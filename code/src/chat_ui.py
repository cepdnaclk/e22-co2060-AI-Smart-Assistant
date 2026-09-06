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
    from src.chatbot_intergrate import chatbot
    await manager.connect(websocket)
    try:
        # Send existing history to the newly connected client
        for msg in chatbot.get_history():
            if msg["role"] == "system":
                continue # skip hidden prompt
            
            sender = "user" if msg["role"] == "user" else "system"
            await websocket.send_text(json.dumps({"sender": sender, "text": msg["content"]}))

        while True:
            data = await websocket.receive_text()
            # Echo the user's message back so it appears in the chat
            await manager.broadcast({"sender": "user", "text": data})

            # Call Mistral via the chatbot integration (which uses user memory and profile)
            def call_mistral(prompt):
                return chatbot.continue_conversation(prompt)

            loop = asyncio.get_event_loop()
            ai_reply = await loop.run_in_executor(None, call_mistral, data)
            await manager.broadcast({"sender": "system", "text": ai_reply})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
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