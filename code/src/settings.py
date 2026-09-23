import copy
import json
import os
import re

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

DEFAULTS = {
    "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "serial_port": "COM3",
    "baud_rate": 9600,
    "general": {
        "theme": "dark",
        "font_size": "medium",
        "typing_animation": True,
        "typing_speed": 18,
        "always_on_top": True,
        "window_opacity": 0.8,
    },
    "model": {
        "provider": "ollama",
        # 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and adds ~2s per request
        "ollama_url": "http://127.0.0.1:11434",
        "model": "mistral",
        "temperature": 0.7,
        "max_tokens": 512,
    },
    "capture": {
        "capture_hotkey": "ctrl+alt+shift+o",
        "exit_hotkey": "ctrl+alt+shift+p",
        "auto_copy": True,
        "save_ai_solutions": True,
        "match_threshold": 0.6,
    },
}

# -------------------------- Validators --------------------------
MODIFIERS = {"ctrl", "alt", "shift", "windows"}
KEY_PATTERN = re.compile(r"^[a-z0-9]+$")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _choice(*options):
    def check(value):
        if value not in options:
            return f"Must be one of: {', '.join(options)}"
    return check


def _boolean(value):
    if not isinstance(value, bool):
        return "Must be true or false"


def _number(low, high, integer=False):
    def check(value):
        if not _is_number(value) or (integer and not isinstance(value, int)):
            return "Must be a whole number" if integer else "Must be a number"
        if not low <= value <= high:
            return f"Must be between {low} and {high}"
    return check


def _text(value):
    if not isinstance(value, str) or not value.strip():
        return "Must not be empty"


def _url(value):
    if not isinstance(value, str) or not value.startswith(("http://", "https://")):
        return "Must start with http:// or https://"


def _hotkey(value):
    if not isinstance(value, str):
        return "Must be a key combination"
    parts = [p.strip() for p in value.lower().split("+")]
    modifiers = [p for p in parts if p in MODIFIERS]
    keys = [p for p in parts if p not in MODIFIERS]
    if not modifiers:
        return "Must include Ctrl, Alt, Shift or Windows"
    if len(keys) != 1 or not KEY_PATTERN.match(keys[0]):
        return "Must include exactly one normal key"
    if len(set(modifiers)) != len(modifiers):
        return "Modifier keys must not repeat"


RULES = {
    "tesseract_cmd": _text,
    "serial_port": _text,
    "baud_rate": _number(1, 4_000_000, integer=True),
    "general": {
        "theme": _choice("dark", "light", "system"),
        "font_size": _choice("small", "medium", "large"),
        "typing_animation": _boolean,
        "typing_speed": _number(5, 60, integer=True),
        "always_on_top": _boolean,
        "window_opacity": _number(0.6, 1.0),
    },
    "model": {
        "provider": _choice("ollama"),
        "ollama_url": _url,
        "model": _text,
        "temperature": _number(0.0, 1.5),
        "max_tokens": _number(64, 4096, integer=True),
    },
    "capture": {
        "capture_hotkey": _hotkey,
        "exit_hotkey": _hotkey,
        "auto_copy": _boolean,
        "save_ai_solutions": _boolean,
        "match_threshold": _number(0.4, 0.9),
    },
}

# -------------------------- Helpers --------------------------
def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _collect_errors(values: dict, rules: dict, prefix: str = "") -> dict:
    """Return {"section.key": message} for every invalid or unknown value."""
    errors = {}
    for key, value in values.items():
        path = f"{prefix}{key}"
        rule = rules.get(key)
        if rule is None:
            errors[path] = "Unknown setting"
        elif isinstance(rule, dict):
            if not isinstance(value, dict):
                errors[path] = "Must be a group of settings"
            else:
                errors.update(_collect_errors(value, rule, f"{path}."))
        else:
            message = rule(value)
            if message:
                errors[path] = message
    return errors


def _normalize_hotkeys(values: dict):
    capture = values.get("capture")
    if isinstance(capture, dict):
        for key in ("capture_hotkey", "exit_hotkey"):
            if isinstance(capture.get(key), str):
                capture[key] = "+".join(p.strip() for p in capture[key].lower().split("+"))


def _read_file() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        print(f"[Settings] Could not read config.json, using defaults: {e}")
        return {}


def _write_file(settings: dict):
    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)
    os.replace(tmp_path, CONFIG_PATH)

# -------------------------- Public API --------------------------
def validate(partial: dict, current: dict = None) -> dict:
    """
    Validate a partial update like {"model": {"temperature": 0.5}}.
    Returns {"section.key": message}; empty dict means valid.
    """
    partial = copy.deepcopy(partial)
    _normalize_hotkeys(partial)
    errors = _collect_errors(partial, RULES)

    merged = _deep_merge(current or load_settings(), partial)
    capture = merged["capture"]
    if capture["capture_hotkey"] == capture["exit_hotkey"]:
        key = "exit_hotkey" if "exit_hotkey" in partial.get("capture", {}) else "capture_hotkey"
        errors.setdefault(f"capture.{key}", "Capture and exit hotkeys must be different")
    return errors


def load_settings() -> dict:
    """Load config.json merged over DEFAULTS. Invalid values fall back to defaults."""
    stored = _read_file()
    _normalize_hotkeys(stored)
    settings = _deep_merge(DEFAULTS, stored)

    for path, message in _collect_errors(stored, RULES).items():
        if message == "Unknown setting":
            continue  # keep unknown keys untouched
        section, _, key = path.partition(".")
        if key:
            settings[section][key] = copy.deepcopy(DEFAULTS[section][key])
        else:
            settings[section] = copy.deepcopy(DEFAULTS[section])
        print(f"[Settings] Invalid value for {path} ({message}); using default.")

    capture = settings["capture"]
    if capture["capture_hotkey"] == capture["exit_hotkey"]:
        print("[Settings] Capture and exit hotkeys are the same; using defaults.")
        capture["capture_hotkey"] = DEFAULTS["capture"]["capture_hotkey"]
        capture["exit_hotkey"] = DEFAULTS["capture"]["exit_hotkey"]
    return settings


def save_settings(partial: dict):
    """
    Validate and save a partial update.
    Returns (settings, errors). Nothing is written when errors is not empty.
    """
    current = load_settings()
    errors = validate(partial, current)
    if errors:
        return current, errors

    partial = copy.deepcopy(partial)
    _normalize_hotkeys(partial)
    settings = _deep_merge(current, partial)
    _write_file(settings)
    return settings, {}


def reset_settings() -> dict:
    """Restore every setting to its default value."""
    settings = copy.deepcopy(DEFAULTS)
    _write_file(settings)
    return settings
