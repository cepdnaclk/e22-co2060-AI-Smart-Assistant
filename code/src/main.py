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
from src.ai_module.rag import rag_query, build_faiss_index, cache_suggestion
import subprocess

from src.ocr_module.overlay import RegionSelection
from src.ocr_module.engine import OCREngine
from src.automation.comms import copy_to_clipboard
from src.ai_module.client import MistralClient
from src import chat_ui  # Tkinter chat window module

# -------------------------- DPI Awareness --------------------------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

# -------------------------- Config Paths --------------------------
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
DB_FILE = os.path.join(os.path.dirname(__file__), 'errors_db.json')

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {}

config = load_config()
TESSERACT_CMD = config.get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

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
    capture_event.set()

def run_capture_logic():
    global is_processing
    print("Hotkey triggered!")
    try:
        region_selector = RegionSelection()
        selection = region_selector.get_region()
        if not selection:
            print("Selection cancelled.")
            return

        text = ocr.capture_and_extract(selection)
        if not text:
            print("No text detected.")
            return

        print(f"Extracted Text: {text}")
        copy_to_clipboard(text)

        if chat_queue:
            chat_queue.put(text)

        # Check local DB
        solution = find_error_solution(text)
        if solution:
            print(f"[LOCAL DB MATCH] Category: {solution['category']}")
            suggestion = solution['solution']
            print(f"Suggested Fix: {suggestion}")
            if chat_queue:
                chat_queue.put({"sender": "system", "text": suggestion})
        else:
            print("[LOCAL DB] No match found. Using RAG fallback...")
            # --- RAG Retrieval ---
            suggestion = rag_query(text)
            print(f"[RAG SUGGESTION] {suggestion}")

        # Cache suggestion
        cache_suggestion(text, suggestion)

        # 2. Send the AI Suggestion to the UI as 'system'
        if chat_queue:
            chat_queue.put({"sender": "system", "text": suggestion})
        
        
    except Exception as e:
        print(f"Error in capture logic: {e}")
    finally:
        is_processing = False


# -------------------------- Hotkeys & Tray --------------------------
def setup_hotkey():
    keyboard.add_hotkey('ctrl+alt+shift+o', trigger_capture)
    keyboard.add_hotkey('ctrl+alt+shift+p', exit_app_hotkey)

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

    # --- NEW: Build FAISS index from JSON DB ---
    build_faiss_index()

    # Start chat UI process (FastAPI server)
    chat_queue, chat_process = chat_ui.start_chat_process()

    # Start Electron UI Subprocess
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
