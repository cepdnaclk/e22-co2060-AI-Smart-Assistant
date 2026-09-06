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
import shutil
from src.ai_module.rag import rag_query, build_faiss_index, cache_suggestion
import subprocess

from src.ocr_module.overlay import RegionSelection
from src.ocr_module.engine import OCREngine
from src.automation.comms import copy_to_clipboard
from src.ai_module.client import MistralClient
from src import chat_ui  # Tkinter chat window module
import requests
from bs4 import BeautifulSoup
from src.ai_module.search_module import web_search_tavily
from src.ai_module.client import MistralClient

# -------------------------- DPI Awareness --------------------------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

# -------------------------- Config Paths --------------------------
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
SOURCE_DB_FILE = os.path.join(os.path.dirname(__file__), 'errors_db.json')
DATA_DIR = os.environ.get("AI_ASSISTANT_DATA_DIR")
if DATA_DIR:
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_FILE = os.path.join(DATA_DIR, 'errors_db.json')
    if not os.path.exists(DB_FILE) and os.path.exists(SOURCE_DB_FILE):
        shutil.copy2(SOURCE_DB_FILE, DB_FILE)
else:
    DB_FILE = SOURCE_DB_FILE
CAPTURE_REQUEST_FILE = os.path.join(DATA_DIR, "capture.request") if DATA_DIR else None

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {}

config = load_config()
TESSERACT_CMD = config.get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if not os.path.exists(TESSERACT_CMD):
    bundled_tesseract = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tesseract', 'tesseract.exe'))
    if os.path.exists(bundled_tesseract):
        TESSERACT_CMD = bundled_tesseract

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

def find_error_solution(text: str):
    db = load_db()
    normalized = normalize_text(text)

    print("Normalized OCR:", normalized)
    for key, value in db.items():
        if key in normalized:
            print(f"✅ Exact match: {key}")
            return value
        ratio = difflib.SequenceMatcher(None, key, normalized).ratio()
        if ratio > 0.6:
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
    # Hide chat window so it cannot interfere with region selection
    if chat_queue:
        chat_queue.put({"action": "hide"})
    capture_event.set()



def run_capture_logic():
    global is_processing
    print("Hotkey triggered!")
    try:
        time.sleep(0.4)
        region_selector = RegionSelection()
        selection = region_selector.get_region()
        if not selection:
            print("Selection cancelled.")
            return

        if ocr is None:
            raise RuntimeError("OCR is unavailable. Check the Tesseract installation.")

        text = ocr.capture_and_extract(selection)
        if not text:
            print("No text detected.")
            return

        print(f"Extracted Text: {text}")
        copy_to_clipboard(text)

        if chat_queue:
            chat_queue.put({"sender": "system", "text": f"OCR Input: {text}", "role": "user"})

        # --- DB + RAG logic ---
        solution = find_error_solution(text)
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

        # --- Web Search fallback ---
        if not suggestion or suggestion.strip() in ["", "N/A", "unavailable", "⚠️ AI suggestion unavailable. Make sure Ollama is running (`ollama run mistral`)."]:
            print("[RAG] No useful suggestion. Falling back to Web Search...")
            search_results = web_search_tavily(text)

            # Always print what Tavily returned
            print(f"[DEBUG] Tavily raw results: {search_results}")

            if search_results:
                print(f"[DEBUG] Tavily returned {len(search_results)} results")
                for idx, r in enumerate(search_results, 1):
                    print(f"[DEBUG] Result {idx}: {r}")

                context = "\n".join(search_results)
                prompt = f"Summarize and answer based on these search results:\n{context}\n\nQuestion: {text}"
                suggestion = MistralClient().chat(prompt)
            else:
                print("[DEBUG] Tavily returned no results")
                suggestion = "⚠️ No web search results found."

        # Cache suggestion only when it's real AI content (not a fallback warning)
        is_real_suggestion = (
            (solution is None or not solution.get('solution'))
            and suggestion
            and not suggestion.startswith("⚠️")
        )
        if is_real_suggestion:
            print(f"[DB] Saving new entry to errors_db.json...")
            cache_suggestion(text, suggestion)
            print(f"[DB] Saved successfully.")

        # Send the AI Suggestion to the UI
        if chat_queue:
            chat_queue.put({"sender": "system", "text": suggestion})

    except Exception as e:
        print(f"Error in capture logic: {e}")
        if chat_queue:
            chat_queue.put({"sender": "system", "text": f"Capture processing failed: {e}"})
    finally:
        is_processing = False


# -------------------------- Hotkeys & Tray --------------------------
def setup_hotkey():
    if not CAPTURE_REQUEST_FILE:
        keyboard.add_hotkey('ctrl+alt+shift+o', trigger_capture)
    keyboard.add_hotkey('ctrl+alt+shift+p', exit_app_hotkey)

def check_capture_request():
    if not CAPTURE_REQUEST_FILE or not os.path.exists(CAPTURE_REQUEST_FILE):
        return
    try:
        os.remove(CAPTURE_REQUEST_FILE)
        trigger_capture()
    except OSError as e:
        print(f"Capture request error: {e}")

def start_tray_icon():
    global icon
    icon = pystray.Icon("OCR Tool")
    icon.menu = pystray.Menu(pystray.MenuItem('Quit', on_quit))
    icon.icon = create_icon_image()
    icon.title = "OCR Tool"
    icon.run()

# -------------------------- Main --------------------------
def main():
    global chat_queue
    global electron_process

    setup_hotkey()
    print("Background OCR Service Running...")
    print("Capture: Ctrl+Alt+Shift+O | Exit: Ctrl+Alt+Shift+P")
    print("Open chat: Ctrl+Alt+Shift+C")

    # --- Build FAISS index in background so startup is not blocked ---
    faiss_thread = threading.Thread(target=build_faiss_index, daemon=True, name="faiss-index-builder")
    faiss_thread.start()
    print("[RAG] FAISS index building in background...")

    # Start chat UI process (FastAPI server)
    from src import chatbot_intergrate
    chat_queue, chat_process = chatbot_intergrate.start_chat_process()

    # Packaged Electron starts this service; development mode starts Electron here.
    if os.environ.get("AI_ASSISTANT_ELECTRON_MANAGED") == "1":
        print("Electron-managed mode: using the parent desktop application.")
    else:
        electron_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'electron_ui'))
        try:
            electron_process = subprocess.Popen(["cmd.exe", "/c", "npm start"], cwd=electron_dir)
            print("Electron UI started successfully.")
        except Exception as e:
            print(f"Failed to start Electron UI: {e}")

    # Start tray icon thread
    tray_thread = threading.Thread(target=start_tray_icon, daemon=True)
    tray_thread.start()

    while running:
        check_capture_request()
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
