import multiprocessing
import queue
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from src.ai_module.client import MistralClient

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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo the user's message back so it appears in the chat
            await manager.broadcast({"sender": "user", "text": data})

            # Call Mistral in a thread so we don't block the event loop
            def call_mistral(prompt):
                client = MistralClient()
                result = client.generate(
                    f"You are a helpful AI assistant.\nUser: {prompt}\nAssistant:"
                )
                return result.get("response") or "⚠️ AI unavailable. Make sure Ollama is running (`ollama run mistral`)."

            loop = asyncio.get_event_loop()
            ai_reply = await loop.run_in_executor(None, call_mistral, data)
            await manager.broadcast({"sender": "system", "text": ai_reply})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def check_queue(msg_queue: multiprocessing.Queue):
    while True:
        try:
            # Non-blocking get from multiprocessing queue
            msg_data = msg_queue.get_nowait()
            if msg_data:
                if isinstance(msg_data, dict):
                    sender = msg_data.get("sender", "system")
                    message = msg_data.get("text", "")
                else:
                    sender = "system"
                    message = msg_data
                
                # Broadcast the message to all connected Flutter clients
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

def _run_server(msg_queue):
    global global_msg_queue
    global_msg_queue = msg_queue
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

def start_chat_process():
    """
    Spawns a new process running the FastAPI ASGI server instead of Tkinter.
    Maintains the same interface so main.py doesn't need modifications.
    """
    msg_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_run_server, args=(msg_queue,), daemon=True)
    p.start()
    return msg_queue, p