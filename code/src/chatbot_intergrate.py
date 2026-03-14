from src.ai_module.client import MistralClient
import multiprocessing
import src.chat_ui as chat_ui

class ChatbotIntegration:
    def __init__(self):
        self.client = MistralClient()
        # Initialize conversation history with a system prompt
        self.history = [{"role": "system", "content": "You are a helpful AI assistant."}]

    def continue_conversation(self, user_message: str) -> str:
        """
        Appends the user's message to the history, gets the AI response,
        appends the AI response to the history, and returns it.
        """
        self.history.append({"role": "user", "content": user_message})
        
        # Use the chat() method which handles message history
        result = self.client.chat(self.history)
        
        response_text = result.get("response")
        if not response_text:
            err_msg = result.get("error", "Unknown error")
            response_text = f"⚠️ AI unavailable: {err_msg}. Make sure Ollama is running (`ollama run mistral`) and not timing out."
        
        # Append assistant's response to history
        self.history.append({"role": "assistant", "content": response_text})
        
        return response_text

# Global singleton instance so the history persists across calls processing
chatbot = ChatbotIntegration()

def get_chatbot_response(message: str) -> str:
    """Wrapper function to easily call from main.py"""
    return chatbot.continue_conversation(message)

# --- PATCH FOR FASTAPI BACKEND ---

class PatchedMistralClient:
    def __init__(self, *args, **kwargs):
        pass
        
    def generate(self, prompt: str, *args, **kwargs) -> dict:
        # Extract the original user message from chat_ui's format
        # chat_ui sends: "You are a helpful AI assistant.\nUser: {prompt}\nAssistant:"
        user_message = prompt
        prefix = "You are a helpful AI assistant.\nUser: "
        suffix = "\nAssistant:"
        if prefix in user_message:
            user_message = user_message.split(prefix, 1)[1]
        if user_message.endswith(suffix):
            user_message = user_message.rsplit(suffix, 1)[0]
            
        # Use our memory-enabled singleton chatbot
        res = chatbot.continue_conversation(user_message.strip())
        return {"response": res}

def _patched_run_server(msg_queue):
    # Monkey-patch MistralClient in chat_ui so it uses our history-aware client
    chat_ui.MistralClient = PatchedMistralClient
    chat_ui._run_server(msg_queue)

def start_chat_process():
    """Starts the FastAPI chat process using the patched client"""
    msg_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_patched_run_server, args=(msg_queue,), daemon=True)
    p.start()
    return msg_queue, p
