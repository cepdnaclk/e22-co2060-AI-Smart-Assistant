import json
import time
import threading
import keyboard
import pystray
from PIL import Image, ImageDraw
import os
import re
import difflib
import ctypes
import multiprocessing
import queue
import socket
from src.ai_module.rag import rag_query, build_faiss_index, cache_suggestion, rebuild_index
import subprocess
import urllib.request
import urllib.error

from src.ocr_module.overlay import RegionSelection
from src.ocr_module.engine import OCREngine
from src.automation.comms import copy_to_clipboard
from src.ai_module.client import MistralClient
from src import chat_ui  # Tkinter chat window module
from src.settings import load_settings, DEFAULTS

# -------------------------- DPI Awareness --------------------------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

# -------------------------- Config Paths --------------------------
DB_FILE = os.path.join(os.path.dirname(__file__), 'errors_db.json')

settings = load_settings()
TESSERACT_CMD = settings["tesseract_cmd"]

# -------------------------- Globals --------------------------
ocr = None
icon = None
running = True
capture_event = threading.Event()
is_processing = False
chat_queue = None
electron_process = None

# -------------------------- Initialize OCR --------------------------
try:
    ocr = OCREngine(TESSERACT_CMD)
except Exception as e:
    print(f"OCR Engine Init Error: {e}")

# -------------------------- Error DB Helpers --------------------------
def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9.\s]", " ", text)  # keep letters, numbers, dot, space
    return " ".join(text.split())

def load_db() -> dict:
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k.lower(): v for k, v in raw.items()}

def find_error_solution(text: str, threshold: float = 0.6):
    db = load_db()
    normalized = normalize_text(text)

    print("Normalized OCR:", normalized)
    for key, value in db.items():
        if key in normalized:
            print(f"✅ Exact match: {key}")
            return value
        ratio = difflib.SequenceMatcher(None, key, normalized).ratio()
        if ratio > threshold:
            print(f"🤏 Fuzzy match: {key} (score {ratio:.2f})")
            return value
    print("❌ No match found")
    return None

# -------------------------- Tray Icon --------------------------
def create_icon_image():
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), color=(0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.rectangle((16, 16, 48, 48), fill=(0, 0, 0))
    return image

def on_quit(icon_obj, item):
    global running
    running = False
    icon_obj.stop()

def exit_app_hotkey():
    global running
    print("Exit hotkey pressed. Exiting...")
    if chat_queue:
        chat_queue.put({"action": "quit"})
    
    # Wait half a second so the quit action can be broadcasted to the UI
    time.sleep(0.5)
    running = False
    if icon:
        icon.stop()

# -------------------------- Capture Logic --------------------------
def trigger_capture():
    global is_processing
    if is_processing:
        print("Capture in progress... ignoring press.")
        return
    is_processing = True
    # Hide chat window so it's out of the way during region selection
    if chat_queue:
        chat_queue.put({"action": "hide"})
    capture_event.set()

def run_capture_logic():
    global is_processing
    print("Hotkey triggered!")
    capture_settings = load_settings()["capture"]
    try:
        time.sleep(0.4)
        region_selector = RegionSelection()
        selection = region_selector.get_region()
        if not selection:
            print("Selection cancelled.")
            return

        # Give the OS time to destroy the Tkinter overlay window before capturing the screen
        time.sleep(0.3)
        text = ocr.capture_and_extract(selection)
        if not text:
            print("No text detected.")
            return

        print(f"Extracted Text: {text}")
        if capture_settings["auto_copy"]:
            copy_to_clipboard(text)

        if chat_queue:
            chat_queue.put({"sender": "system", "text": f"OCR Input: {text}", "role": "user"})

        # --- DB + RAG logic ---
        solution = find_error_solution(text, capture_settings["match_threshold"])
        suggestion = None

        if solution:
            print(f"[LOCAL DB MATCH] Category: {solution.get('category')}")
            suggestion = solution.get('solution')

            # If DB entry is empty or placeholder, fallback to RAG
            if not suggestion or suggestion.strip() in ["", "N/A", "unavailable"]:
                print("[LOCAL DB] Entry incomplete. Falling back to RAG...")
                suggestion = rag_query(text)
        else:
            print("[LOCAL DB] No match found. Using RAG fallback...")
            suggestion = rag_query(text)

        # Guard: if AI returned nothing (e.g. Mistral offline)
        if not suggestion:
            suggestion = "⚠️ AI suggestion unavailable. Make sure Ollama is running (`ollama run mistral`)."

        # Cache suggestion only when it's real AI content (not a fallback warning)
        is_real_suggestion = (
            (solution is None or not solution.get('solution'))  # either no DB or incomplete DB
            and suggestion
            and not suggestion.startswith("⚠️")
        )
        if is_real_suggestion and not capture_settings["save_ai_solutions"]:
            print("[DB] Learning new solutions is turned off. Not saving.")
        elif is_real_suggestion:
            print(f"[DB] Saving new entry to errors_db.json...")
            cache_suggestion(text, suggestion)
            print(f"[DB] Saved successfully.")

        # Send the AI Suggestion to the UI
        if chat_queue:
            chat_queue.put({"sender": "system", "text": suggestion})

    except Exception as e:
        print(f"Error in capture logic: {e}")
    finally:
        is_processing = False


# -------------------------- Hotkeys & Tray --------------------------
def setup_hotkey():
    """Register the capture/exit hotkeys from settings. Returns (capture, exit) actually in use."""
    capture_settings = load_settings()["capture"]
    capture_hotkey = capture_settings["capture_hotkey"]
    exit_hotkey = capture_settings["exit_hotkey"]
    try:
        keyboard.add_hotkey(capture_hotkey, trigger_capture)
        keyboard.add_hotkey(exit_hotkey, exit_app_hotkey)
    except ValueError as e:
        # The keyboard library rejected a key name; fall back to the defaults
        print(f"Invalid hotkey in settings ({e}). Using defaults.")
        keyboard.unhook_all_hotkeys()
        capture_hotkey = DEFAULTS["capture"]["capture_hotkey"]
        exit_hotkey = DEFAULTS["capture"]["exit_hotkey"]
        keyboard.add_hotkey(capture_hotkey, trigger_capture)
        keyboard.add_hotkey(exit_hotkey, exit_app_hotkey)
    return capture_hotkey, exit_hotkey

def apply_settings(rebuild=False):
    """Apply settings saved from the UI: re-register hotkeys, reload OCR, rebuild RAG index."""
    global ocr, TESSERACT_CMD
    settings = load_settings()

    keyboard.unhook_all_hotkeys()
    capture_hotkey, exit_hotkey = setup_hotkey()
    print(f"[Settings] Applied. Capture: {capture_hotkey} | Exit: {exit_hotkey}")

    if settings["tesseract_cmd"] != TESSERACT_CMD:
        try:
            ocr = OCREngine(settings["tesseract_cmd"])
            TESSERACT_CMD = settings["tesseract_cmd"]
            print(f"[Settings] OCR now uses {TESSERACT_CMD}")
        except Exception as e:
            print(f"[Settings] Could not load Tesseract, keeping previous one: {e}")

    if rebuild:
        threading.Thread(target=rebuild_index, daemon=True, name="faiss-index-rebuilder").start()
        print("[RAG] Rebuilding FAISS index in background...")

def start_tray_icon():
    global icon
    icon = pystray.Icon("OCR Tool")
    icon.menu = pystray.Menu(pystray.MenuItem('Quit', on_quit))
    icon.icon = create_icon_image()
    icon.title = "OCR Tool"
    icon.run()

def select_chat_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]

def check_ollama_status(chat_queue):
    # Wait a moment for UI to fully load
    time.sleep(2)
    try:
        # 1. Check if Ollama is running
        try:
            urllib.request.urlopen("http://localhost:11434/", timeout=2)
        except Exception:
            if chat_queue:
                chat_queue.put({"sender": "system", "text": "🔄 **Starting Ollama engine in the background...**"})
            try:
                # Attempt to auto-start Ollama quietly
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.Popen(["ollama", "serve"], startupinfo=startupinfo)
                time.sleep(5) # Wait for it to spin up
                urllib.request.urlopen("http://localhost:11434/", timeout=3)
            except Exception:
                if chat_queue:
                    chat_queue.put({"sender": "system", "text": "⚠️ **Ollama is not installed.**\n\nPlease install it using the provided setup file."})
                return

        # 2. Check if Mistral is installed
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            if "mistral" not in result.stdout:
                if chat_queue:
                    chat_queue.put({"sender": "system", "text": "⏳ **Downloading AI Brain (Mistral)**...\n\nThis is a one-time 4GB download. It may take a few minutes depending on your internet connection. Please do not close the app!"})
                
                # Pull the model
                pull_result = subprocess.run(["ollama", "pull", "mistral"], capture_output=True, text=True)
                
                if pull_result.returncode == 0:
                    if chat_queue:
                        chat_queue.put({"sender": "system", "text": "✅ **Download Complete!** The AI is now ready to assist you."})
                else:
                    if chat_queue:
                        chat_queue.put({"sender": "system", "text": f"❌ **Failed to download.**\n```\n{pull_result.stderr}\n```"})
        except Exception as e:
            if chat_queue:
                chat_queue.put({"sender": "system", "text": f"❌ **Error communicating with Ollama:** {e}"})
    except Exception as e:
        print(f"Startup check error: {e}")


# -------------------------- Main --------------------------
def main():
    global chat_queue
    global electron_process

    capture_hotkey, exit_hotkey = setup_hotkey()
    print("Background OCR Service Running...")
    print(f"Capture: {capture_hotkey} | Exit: {exit_hotkey}")

    # --- Build FAISS index in background so startup is not blocked ---
    faiss_thread = threading.Thread(target=build_faiss_index, daemon=True, name="faiss-index-builder")
    faiss_thread.start()
    print("[RAG] FAISS index building in background...")

    # Pick a free port so an orphaned previous server cannot block startup.
    os.environ["CHAT_SERVER_PORT"] = str(select_chat_port())
    print(f"Chat server port: {os.environ['CHAT_SERVER_PORT']}")

    # Start chat UI process (FastAPI server)
    from src import chatbot_intergrate
    chat_queue, capture_control_queue, chat_process = chatbot_intergrate.start_chat_process()

    # Start Electron UI Subprocess (only in dev mode)
    import sys
    if not getattr(sys, 'frozen', False):
        electron_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'electron_ui'))
        try:
            electron_process = subprocess.Popen(["cmd.exe", "/c", "npm start"], cwd=electron_dir)
            print("Electron UI started successfully.")
        except Exception as e:
            print(f"Failed to start Electron UI: {e}")

    # Start tray icon thread
    tray_thread = threading.Thread(target=start_tray_icon, daemon=True)
    tray_thread.start()

    # Start Ollama status check in background
    threading.Thread(target=check_ollama_status, args=(chat_queue,), daemon=True).start()

    while running:
        try:
            while True:
                control_message = capture_control_queue.get_nowait()
                if control_message.get("action") == "capture":
                    trigger_capture()
                elif control_message.get("action") == "settings_updated":
                    apply_settings(rebuild=control_message.get("rebuild_index", False))
                elif control_message.get("action") == "pause_hotkeys":
                    # The settings page is recording a new hotkey; don't trigger capture/exit meanwhile
                    keyboard.unhook_all_hotkeys()
                    print("[Settings] Hotkeys paused while recording.")
                elif control_message.get("action") == "resume_hotkeys":
                    keyboard.unhook_all_hotkeys()
                    setup_hotkey()
                    print("[Settings] Hotkeys resumed.")
        except queue.Empty:
            pass

        if capture_event.is_set():
            capture_event.clear()
            run_capture_logic()
        time.sleep(0.1)

    print("Exiting program...")
    if chat_process.is_alive():
        chat_process.terminate()
    if electron_process:
        electron_process.terminate()
        # Fallback for Windows to forcefully kill the cmd tree if necessary
        os.system(f"taskkill /f /pid {electron_process.pid} /t >nul 2>&1")
    os._exit(0)



if __name__ == "__main__":
    main()
