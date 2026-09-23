import json
import os
import tempfile
import unittest

from src import settings


class SettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.original_path = settings.CONFIG_PATH
        settings.CONFIG_PATH = os.path.join(self.tmp_dir.name, "config.json")

    def tearDown(self):
        settings.CONFIG_PATH = self.original_path
        self.tmp_dir.cleanup()

    def write_config(self, data):
        with open(settings.CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def read_config(self):
        with open(settings.CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    # -------------------------- load_settings --------------------------
    def test_missing_file_returns_defaults(self):
        self.assertEqual(settings.load_settings(), settings.DEFAULTS)

    def test_old_style_config_is_merged_with_defaults(self):
        self.write_config({"tesseract_cmd": "D:\\tess.exe", "serial_port": "COM5", "baud_rate": 9600})
        loaded = settings.load_settings()
        self.assertEqual(loaded["tesseract_cmd"], "D:\\tess.exe")
        self.assertEqual(loaded["serial_port"], "COM5")
        self.assertEqual(loaded["model"], settings.DEFAULTS["model"])
        self.assertEqual(loaded["capture"], settings.DEFAULTS["capture"])

    def test_invalid_stored_value_falls_back_to_default(self):
        self.write_config({"model": {"temperature": 99, "model": "llama3"}})
        loaded = settings.load_settings()
        self.assertEqual(loaded["model"]["temperature"], settings.DEFAULTS["model"]["temperature"])
        self.assertEqual(loaded["model"]["model"], "llama3")

    def test_broken_json_returns_defaults(self):
        with open(settings.CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write("{ not json")
        self.assertEqual(settings.load_settings(), settings.DEFAULTS)

    def test_duplicate_stored_hotkeys_fall_back_to_defaults(self):
        self.write_config({"capture": {"capture_hotkey": "ctrl+k", "exit_hotkey": "ctrl+k"}})
        capture = settings.load_settings()["capture"]
        self.assertEqual(capture["capture_hotkey"], settings.DEFAULTS["capture"]["capture_hotkey"])
        self.assertEqual(capture["exit_hotkey"], settings.DEFAULTS["capture"]["exit_hotkey"])

    # -------------------------- validate --------------------------
    def test_validate_accepts_good_values(self):
        self.assertEqual(settings.validate({"model": {"temperature": 0.2, "max_tokens": 1024}}), {})

    def test_validate_rejects_out_of_range_temperature(self):
        errors = settings.validate({"model": {"temperature": 3}})
        self.assertIn("model.temperature", errors)

    def test_validate_rejects_bool_as_number(self):
        errors = settings.validate({"model": {"max_tokens": True}})
        self.assertIn("model.max_tokens", errors)

    def test_validate_rejects_unknown_keys(self):
        errors = settings.validate({"general": {"colour": "red"}, "nonsense": 1})
        self.assertIn("general.colour", errors)
        self.assertIn("nonsense", errors)

    def test_validate_rejects_duplicate_hotkeys(self):
        errors = settings.validate({"capture": {"exit_hotkey": "ctrl+alt+shift+o"}})
        self.assertIn("capture.exit_hotkey", errors)

    def test_validate_rejects_hotkey_without_modifier(self):
        errors = settings.validate({"capture": {"capture_hotkey": "o"}})
        self.assertIn("capture.capture_hotkey", errors)

    def test_validate_rejects_hotkey_with_two_keys(self):
        errors = settings.validate({"capture": {"capture_hotkey": "ctrl+a+b"}})
        self.assertIn("capture.capture_hotkey", errors)

    # -------------------------- save / reset --------------------------
    def test_save_round_trip(self):
        saved, errors = settings.save_settings({"model": {"model": "llama3"}, "general": {"theme": "light"}})
        self.assertEqual(errors, {})
        self.assertEqual(saved["model"]["model"], "llama3")
        self.assertEqual(settings.load_settings(), saved)
        self.assertFalse(os.path.exists(settings.CONFIG_PATH + ".tmp"))

    def test_save_keeps_existing_values(self):
        self.write_config({"serial_port": "COM7"})
        settings.save_settings({"general": {"theme": "light"}})
        self.assertEqual(self.read_config()["serial_port"], "COM7")

    def test_save_normalizes_hotkeys(self):
        saved, errors = settings.save_settings({"capture": {"capture_hotkey": "Ctrl + Shift + K"}})
        self.assertEqual(errors, {})
        self.assertEqual(saved["capture"]["capture_hotkey"], "ctrl+shift+k")

    def test_invalid_save_writes_nothing(self):
        _, errors = settings.save_settings({"general": {"theme": "purple"}})
        self.assertIn("general.theme", errors)
        self.assertFalse(os.path.exists(settings.CONFIG_PATH))

    def test_reset_restores_defaults(self):
        settings.save_settings({"model": {"model": "llama3"}})
        self.assertEqual(settings.reset_settings(), settings.DEFAULTS)
        self.assertEqual(self.read_config(), settings.DEFAULTS)


if __name__ == "__main__":
    unittest.main()
