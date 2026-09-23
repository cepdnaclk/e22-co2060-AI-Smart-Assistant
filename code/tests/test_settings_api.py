import json
import os
import queue
import tempfile
import unittest

from src import chat_ui, settings
from src.ai_module import rag
from src.memory import user_profile
from src.chatbot_intergrate import chatbot


class SettingsApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        tmp = self.tmp_dir.name
        self.originals = (settings.CONFIG_PATH, user_profile.PROFILE_FILE, rag.DB_FILE, chat_ui.global_control_queue)
        settings.CONFIG_PATH = os.path.join(tmp, "config.json")
        user_profile.PROFILE_FILE = os.path.join(tmp, "user_profile.json")
        rag.DB_FILE = os.path.join(tmp, "errors_db.json")
        chat_ui.global_control_queue = queue.Queue()
        chatbot.clear_history()

    def tearDown(self):
        settings.CONFIG_PATH, user_profile.PROFILE_FILE, rag.DB_FILE, chat_ui.global_control_queue = self.originals
        chatbot.clear_history()
        self.tmp_dir.cleanup()

    def call(self, **request):
        return chat_ui.handle_settings_action(request)

    def control_messages(self):
        messages = []
        while not chat_ui.global_control_queue.empty():
            messages.append(chat_ui.global_control_queue.get_nowait())
        return messages

    def test_get_settings_returns_settings_and_profile(self):
        reply = self.call(action="get_settings")
        self.assertEqual(reply["action"], "settings")
        self.assertEqual(reply["settings"], settings.DEFAULTS)
        self.assertTrue(reply["profile"]["personalization_enabled"])

    def test_save_settings_saves_and_notifies_main_process(self):
        reply = self.call(action="save_settings", section="model", values={"temperature": 0.2})
        self.assertEqual(reply["action"], "settings_saved")
        self.assertEqual(reply["settings"]["model"]["temperature"], 0.2)
        self.assertEqual(settings.load_settings()["model"]["temperature"], 0.2)
        self.assertEqual(self.control_messages(), [{"action": "settings_updated", "rebuild_index": False}])

    def test_save_settings_rejects_invalid_values(self):
        reply = self.call(action="save_settings", section="capture", values={"capture_hotkey": "k"})
        self.assertEqual(reply["action"], "settings_error")
        self.assertIn("capture.capture_hotkey", reply["errors"])
        self.assertEqual(self.control_messages(), [])

    def test_save_settings_requires_values_object(self):
        reply = self.call(action="save_settings", section="model", values="nope")
        self.assertEqual(reply["action"], "settings_error")

    def test_save_profile_updates_prompt_and_keeps_history(self):
        chatbot.history.append({"role": "user", "content": "hi"})
        reply = self.call(action="save_profile", values={"response_style": "Answer in French."})
        self.assertEqual(reply["action"], "settings_saved")
        self.assertEqual(reply["profile"]["response_style"], "Answer in French.")
        self.assertIn("Answer in French.", chatbot.history[0]["content"])
        self.assertEqual(chatbot.history[-1]["content"], "hi")

    def test_save_profile_rejects_too_long_instructions(self):
        reply = self.call(action="save_profile", values={"about_you": "x" * 1501})
        self.assertEqual(reply["action"], "settings_error")
        self.assertIn("profile.about_you", reply["errors"])

    def test_reset_settings(self):
        self.call(action="save_settings", section="general", values={"theme": "light"})
        reply = self.call(action="reset_settings")
        self.assertEqual(reply["settings"], settings.DEFAULTS)

    def test_delete_learned_solutions_keeps_manual_entries(self):
        with open(rag.DB_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "manual error": {"category": "missing_dll", "solution": "fix"},
                "learned error": {"category": "AI-generated", "solution": "ai fix"},
            }, f)
        reply = self.call(action="delete_learned_solutions")
        self.assertEqual(reply, {"action": "learned_solutions_deleted", "removed": 1})
        with open(rag.DB_FILE, encoding="utf-8") as f:
            self.assertEqual(list(json.load(f)), ["manual error"])
        self.assertEqual(self.control_messages(), [{"action": "settings_updated", "rebuild_index": True}])

    def test_connection_failure_is_reported(self):
        reply = self.call(action="test_connection", url="http://127.0.0.1:1")
        self.assertEqual(reply["action"], "connection_result")
        self.assertFalse(reply["ok"])

    def test_model_actions_work_when_chat_client_is_patched(self):
        # chatbot_intergrate replaces chat_ui.MistralClient with a chat-only client at runtime
        original = chat_ui.MistralClient
        chat_ui.MistralClient = object
        try:
            reply = self.call(action="list_models", url="http://127.0.0.1:1")
        finally:
            chat_ui.MistralClient = original
        self.assertEqual(reply["action"], "models")

    def test_list_models_failure_is_reported(self):
        reply = self.call(action="list_models", url="http://127.0.0.1:1")
        self.assertEqual(reply["models"], [])
        self.assertIsNotNone(reply["error"])


if __name__ == "__main__":
    unittest.main()
