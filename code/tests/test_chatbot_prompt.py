import unittest
from unittest import mock

from src import chatbot_intergrate
from src.chatbot_intergrate import build_system_prompt, ChatbotIntegration

PROFILE = {
    "nickname": "Sooriya",
    "favorite_colours": ["blue", "black"],
    "empty_field": "",
    "personalization_enabled": True,
    "answer_style": "concise",
    "about_you": "I am learning FastAPI.",
    "response_style": "Talk like a pirate.",
}


class BuildSystemPromptTest(unittest.TestCase):
    def test_includes_profile_facts_and_instructions(self):
        prompt = build_system_prompt(PROFILE)
        self.assertIn("Nickname: Sooriya", prompt)
        self.assertIn("Favorite colours: blue, black", prompt)
        self.assertIn("I am learning FastAPI.", prompt)
        self.assertIn("Talk like a pirate.", prompt)
        self.assertIn("Keep answers short", prompt)

    def test_control_keys_and_empty_values_are_not_listed_as_facts(self):
        prompt = build_system_prompt(PROFILE)
        self.assertNotIn("Personalization enabled", prompt)
        self.assertNotIn("About you:", prompt)
        self.assertNotIn("Empty field", prompt)

    def test_disabled_personalization_gives_plain_prompt(self):
        prompt = build_system_prompt({**PROFILE, "personalization_enabled": False})
        self.assertNotIn("Sooriya", prompt)
        self.assertNotIn("pirate", prompt)

    def test_empty_instructions_are_skipped(self):
        prompt = build_system_prompt({"nickname": "Sooriya", "about_you": "  ", "response_style": "", "answer_style": ""})
        self.assertNotIn("What the user wants you to know", prompt)
        self.assertNotIn("How the user wants you to respond", prompt)


class RefreshSettingsTest(unittest.TestCase):
    def test_refresh_updates_system_prompt_and_keeps_history(self):
        with mock.patch.object(chatbot_intergrate, "load_profile", return_value=PROFILE):
            bot = ChatbotIntegration()
        bot.history += [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]

        new_profile = {**PROFILE, "response_style": "Answer in French."}
        with mock.patch.object(chatbot_intergrate, "load_profile", return_value=new_profile):
            bot.refresh_settings()

        self.assertEqual(len(bot.history), 3)
        self.assertIn("Answer in French.", bot.history[0]["content"])
        self.assertNotIn("pirate", bot.history[0]["content"])
        self.assertEqual(bot.history[1]["content"], "hi")


if __name__ == "__main__":
    unittest.main()
