import multiprocessing
import src.chat_ui as chat_ui
from src.ai_module.client import MistralClient
from src.memory.user_profile import load_profile
from src.ai_module.router import handle_user_query
from src.ai_module.router import handle_user_query
from src.ai_module.search_module import web_search_tavily
from src.ai_module.client import MistralClient
from src.ai_module.router import handle_user_query


class ChatbotIntegration:
    def __init__(self):
        self.client = MistralClient()
        self._build_system_prompt()

    def _build_system_prompt(self):
        """Build system prompt dynamically from all user profile fields."""
        profile = load_profile()
        context = []

        # Loop through all keys and values in the profile
        for key, value in profile.items():
            if isinstance(value, list):
                # Join lists into a readable string
                context.append(f"{key.capitalize()}: {', '.join(value)}")
            else:
                context.append(f"{key.capitalize()}: {value}")

        context_str = " ".join(context)

        # Explicitly mark these as USER attributes, not assistant preferences
        self.history = [{
            "role": "system",
            "content": (
                "You are a helpful AI assistant. "
                "The following details describe the USER you are assisting. "
                "Use them to personalize responses, but do not claim them as your own preferences: "
                f"{context_str}"
            )
        }]

    def clear_history(self):
        """Reset conversation history but keep personalization context."""
        self._build_system_prompt()

    def get_history(self):
        return self.history


    def continue_conversation(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        response_text = handle_user_query(user_message, self.history)

        if not response_text:
            response_text = "⚠️ AI unavailable. Make sure Ollama is running (`ollama run mistral`)."

        self.history.append({"role": "assistant", "content": response_text})
        return response_text







# Global singleton instance so the history persists across calls
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
        user_message = prompt
        prefix = "You are a helpful AI assistant.\nUser: "
        suffix = "\nAssistant:"
        if prefix in user_message:
            user_message = user_message.split(prefix, 1)[1]
        if user_message.endswith(suffix):
            user_message = user_message.rsplit(suffix, 1)[0]

        # Pass the raw user message directly
        res = chatbot.continue_conversation(user_message.strip())
        return {"response": res}


def _patched_run_server(msg_queue):
    # Monkey-patch MistralClient in chat_ui so it uses our history-aware client
    chat_ui.MistralClient = PatchedMistralClient
    chat_ui._run_server(msg_queue)


def start_chat_process():
    """Starts the FastAPI chat process using the patched client"""
    msg_queue = multiprocessing.Queue()
    p = multiprocessing.Process(
        target=_patched_run_server,
        args=(msg_queue,),
        daemon=True
    )
    p.start()
    return msg_queue, p