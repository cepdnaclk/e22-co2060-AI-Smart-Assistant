import multiprocessing
import src.chat_ui as chat_ui
from src.ai_module.client import MistralClient
from src.ai_module.router import handle_user_query
from src.memory.user_profile import load_profile, PROFILE_DEFAULTS

ANSWER_STYLES = {
    "concise": "Keep answers short and to the point.",
    "detailed": "Give thorough, detailed explanations with examples where useful.",
}


def build_system_prompt(profile: dict) -> str:
    """Build the system prompt from the user profile and custom instructions."""
    prompt = "You are SENTINEL, a helpful AI assistant."
    if not profile.get("personalization_enabled", True):
        return prompt

    # Profile facts: every key that is not a personalization control
    facts = []
    for key, value in profile.items():
        if key in PROFILE_DEFAULTS or value in ("", None, []):
            continue
        label = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        facts.append(f"{label}: {value}")

    sections = [prompt]
    if facts:
        # Explicitly mark these as USER attributes, not assistant preferences
        sections.append(
            "The following details describe the USER you are assisting. "
            "Use them to personalize responses, but do not claim them as your own preferences:\n"
            + "\n".join(facts)
        )

    about_you = profile.get("about_you", "").strip()
    if about_you:
        sections.append(f"What the user wants you to know about them:\n{about_you}")

    style = profile.get("answer_style", "")
    style_text = ANSWER_STYLES.get(style, f"Answer style: {style}" if style else "")
    response_style = profile.get("response_style", "").strip()
    if style_text or response_style:
        sections.append(
            "How the user wants you to respond (follow this):\n"
            + "\n".join(line for line in (style_text, response_style) if line)
        )

    return "\n\n".join(sections)


class ChatbotIntegration:
    def __init__(self):
        self._build_system_prompt()

    def _system_message(self) -> dict:
        return {"role": "system", "content": build_system_prompt(load_profile())}

    def _build_system_prompt(self):
        """Start a fresh history containing only the system prompt."""
        self.history = [self._system_message()]

    def refresh_settings(self):
        """Re-read the profile and update the system prompt, keeping the conversation."""
        if self.history and self.history[0]["role"] == "system":
            self.history[0] = self._system_message()
        else:
            self.history.insert(0, self._system_message())

    def clear_history(self):
        """Reset conversation history but keep personalization context."""
        self._build_system_prompt()

    def get_history(self):
        return self.history

    def continue_conversation(self, user_message: str) -> str:
        # Add raw user message without artificial prefixes
        self.history.append({"role": "user", "content": user_message})

        # New client per message so model settings changes apply immediately
        response_text = handle_user_query(user_message, self.history)
        if not response_text:
            err_msg = "Unknown error"
            response_text = (
                f"⚠️ AI unavailable: {err_msg}. "
                f"Make sure Ollama is running (`ollama run mistral`)."
            )

        # Append assistant's response to history
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


def _patched_run_server(msg_queue, control_queue):
    # Monkey-patch MistralClient in chat_ui so it uses our history-aware client
    chat_ui.MistralClient = PatchedMistralClient
    chat_ui._run_server(msg_queue, control_queue)


def start_chat_process():
    """Starts the FastAPI chat process using the patched client"""
    msg_queue = multiprocessing.Queue()
    control_queue = multiprocessing.Queue()
    p = multiprocessing.Process(
        target=_patched_run_server,
        args=(msg_queue, control_queue),
        daemon=True
    )
    p.start()
    return msg_queue, control_queue, p