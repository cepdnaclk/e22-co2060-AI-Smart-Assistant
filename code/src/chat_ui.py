import multiprocessing
import queue
import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from src.ai_module.client import MistralClient
from src.ai_module import client as ai_client  # unpatched client for settings (MistralClient is monkey-patched)
from src.ai_module.rag import delete_ai_generated, count_solutions
from src.memory.user_profile import load_profile, save_profile, validate_profile
from src.settings import load_settings, save_settings, reset_settings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error broadcasting message: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# -------------------------- Settings API --------------------------
SETTINGS_ACTIONS = {
    "get_settings", "save_settings", "save_profile", "reset_settings",
    "list_models", "test_connection", "delete_learned_solutions", "get_data_stats",
}

def _notify_main_process(rebuild_index=False):
    """Tell main.py to reload settings (hotkeys, OCR) and optionally rebuild the RAG index."""
    if global_control_queue:
        global_control_queue.put({"action": "settings_updated", "rebuild_index": rebuild_index})

def _settings_snapshot(action: str) -> dict:
    return {"action": action, "settings": load_settings(), "profile": load_profile()}

def _optional_client(request: dict) -> "ai_client.MistralClient":
    """Client for the URL/model in the request (to test before saving), else from settings."""
    url = request.get("url")
    model = request.get("model")
    return ai_client.MistralClient(
        base_url=url if isinstance(url, str) and url else None,
        model=model if isinstance(model, str) and model else None,
    )

def handle_settings_action(request: dict) -> dict:
    """Handle one settings request from the UI. Runs in a worker thread (blocking I/O)."""
    from src.chatbot_intergrate import chatbot
    action = request.get("action")
    try:
        if action == "get_settings":
            return _settings_snapshot("settings")

        if action == "save_settings":
            values = request.get("values")
            section = request.get("section")
            if not isinstance(values, dict):
                return {"action": "settings_error", "errors": {"request": "'values' must be an object"}}
            _, errors = save_settings({section: values} if section else values)
            if errors:
                return {"action": "settings_error", "errors": errors}
            chatbot.refresh_settings()
            _notify_main_process()
            return _settings_snapshot("settings_saved")

        if action == "save_profile":
            values = request.get("values")
            if not isinstance(values, dict):
                return {"action": "settings_error", "errors": {"request": "'values' must be an object"}}
            errors = validate_profile(values)
            if errors:
                return {"action": "settings_error", "errors": {f"profile.{k}": v for k, v in errors.items()}}
            profile = load_profile()
            profile.update(values)
            save_profile(profile)
            chatbot.refresh_settings()
            return _settings_snapshot("settings_saved")

        if action == "reset_settings":
            reset_settings()
            chatbot.refresh_settings()
            _notify_main_process()
            return _settings_snapshot("settings_saved")

        if action == "list_models":
            result = _optional_client(request).list_models()
            return {"action": "models", "models": result["models"], "error": result["error"]}

        if action == "test_connection":
            result = _optional_client(request).ping()
            return {"action": "connection_result", "ok": result["ok"], "detail": result["detail"]}

        if action == "delete_learned_solutions":
            removed = delete_ai_generated()
            if removed:
                _notify_main_process(rebuild_index=True)
            return {"action": "learned_solutions_deleted", "removed": removed}

        if action == "get_data_stats":
            return {"action": "data_stats", **count_solutions()}

    except Exception as e:
        print(f"Settings action '{action}' failed: {e}")
        return {"action": "settings_error", "errors": {"request": str(e)}}

    return {"action": "settings_error", "errors": {"request": f"Unknown action: {action}"}}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from src.chatbot_intergrate import chatbot
    await manager.connect(websocket)

    def last_user_message():
        for message in reversed(chatbot.get_history()):
            if message["role"] == "user":
                return message["content"]
        return None

    async def generate_reply(prompt):
        def call_mistral(message):
            client = MistralClient()
            result = client.generate(
                f"You are a helpful AI assistant.\nUser: {message}\nAssistant:"
            )
            return result.get("response") or "AI unavailable. Make sure Ollama is running (ollama run mistral)."

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, call_mistral, prompt)

    try:
        # Send existing history to the newly connected client
        for msg in chatbot.get_history():
            if msg["role"] == "system":
                continue # skip hidden prompt
            
            sender = "user" if msg["role"] == "user" else "system"
            await websocket.send_text(json.dumps({"sender": sender, "text": msg["content"]}))

        while True:
            data = await websocket.receive_text()

            try:
                request = json.loads(data)
            except json.JSONDecodeError:
                request = None

            if isinstance(request, dict) and request.get("action") == "clear_history":
                chatbot.clear_history()
                await manager.broadcast({"action": "clear"})
                continue

            if isinstance(request, dict) and request.get("action") in SETTINGS_ACTIONS:
                # Reply only to the window that asked; don't broadcast
                loop = asyncio.get_event_loop()
                reply = await loop.run_in_executor(None, handle_settings_action, request)
                # Echo request_id so the UI can tell which page asked (e.g. two pages testing the connection)
                if "request_id" in request:
                    reply["request_id"] = request["request_id"]
                await websocket.send_text(json.dumps(reply))
                continue

            if isinstance(request, dict) and request.get("action") in ("pause_hotkeys", "resume_hotkeys"):
                # Settings page is recording a hotkey: stop the global hotkeys from firing meanwhile
                if global_control_queue:
                    global_control_queue.put({"action": request["action"]})
                continue

            if isinstance(request, dict) and request.get("action") == "capture":
                if global_control_queue:
                    global_control_queue.put({"action": "capture"})
                continue

            if isinstance(request, dict) and request.get("action") == "regenerate":
                prompt = last_user_message()
                if not prompt:
                    continue
                if chatbot.history and chatbot.history[-1]["role"] == "assistant":
                    chatbot.history.pop()
                await manager.broadcast({"action": "remove_last_assistant"})
                ai_reply = await generate_reply(prompt)
                await manager.broadcast({"sender": "system", "text": ai_reply})
                continue

            # Echo the user's message back so it appears in the chat
            await manager.broadcast({"sender": "user", "text": data})

            ai_reply = await generate_reply(data)
            await manager.broadcast({"sender": "system", "text": ai_reply})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Never leave hotkeys paused if the window goes away mid-recording
        if global_control_queue:
            global_control_queue.put({"action": "resume_hotkeys"})
        # Clear the memory when the chat UI window is closed
        chatbot.clear_history()

async def check_queue(msg_queue: multiprocessing.Queue):
    from src.chatbot_intergrate import chatbot
    while True:
        try:
            # Non-blocking get from multiprocessing queue
            msg_data = msg_queue.get_nowait()
            if msg_data:
                # Action messages (e.g. hide, quit) — pass straight to UI, skip history
                if isinstance(msg_data, dict) and "action" in msg_data:
                    await manager.broadcast(msg_data)
                    await asyncio.sleep(0.1)
                    continue

                if isinstance(msg_data, dict):
                    sender = msg_data.get("sender", "system")
                    message = msg_data.get("text", "")
                    role = msg_data.get("role", "assistant" if sender == "system" else "user")
                else:
                    sender = "system"
                    message = msg_data
                    role = "assistant"
                
                # Append to the history so AI remembers them
                chatbot.history.append({"role": role, "content": message})

                # Broadcast the message to all connected clients
                await manager.broadcast({"sender": sender, "text": message})
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error reading queue: {e}")
        
        await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    # Retrieve the queue from the global scope (passed during process creation)
    global global_msg_queue
    if global_msg_queue:
        asyncio.create_task(check_queue(global_msg_queue))

global_msg_queue = None
global_control_queue = None

def _run_server(msg_queue, control_queue=None):
    global global_msg_queue, global_control_queue
    global_msg_queue = msg_queue
    global_control_queue = control_queue
    port = int(os.environ.get("CHAT_SERVER_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

def start_chat_process():
    """
    Spawns a new process running the FastAPI ASGI server instead of Tkinter.
    Maintains the same interface so main.py doesn't need modifications.
    """
    msg_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_run_server, args=(msg_queue, None), daemon=True)
    p.start()
    return msg_queue, p