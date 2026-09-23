import json
import os

PROFILE_FILE = os.path.join(os.path.dirname(__file__), "user_profile.json")

# Settings-style keys that control personalization (not facts about the user)
PROFILE_DEFAULTS = {
    "personalization_enabled": True,
    "answer_style": "concise",
    "about_you": "",
    "response_style": "",
}

INSTRUCTION_LIMIT = 1500  # characters, like ChatGPT's custom instructions
FIELD_LIMIT = 200

def validate_profile(values: dict) -> dict:
    """Return {"key": message} for invalid profile values; empty dict means valid."""
    errors = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key.strip():
            errors[str(key)] = "Invalid field name"
        elif key == "personalization_enabled":
            if not isinstance(value, bool):
                errors[key] = "Must be true or false"
        elif key == "answer_style":
            if value not in ("concise", "detailed"):
                errors[key] = "Must be one of: concise, detailed"
        elif key in ("about_you", "response_style"):
            if not isinstance(value, str):
                errors[key] = "Must be text"
            elif len(value) > INSTRUCTION_LIMIT:
                errors[key] = f"Must be at most {INSTRUCTION_LIMIT} characters"
        elif isinstance(value, list):
            if not all(isinstance(v, str) and len(v) <= FIELD_LIMIT for v in value):
                errors[key] = f"Must be a list of text (each at most {FIELD_LIMIT} characters)"
        elif not isinstance(value, str):
            errors[key] = "Must be text"
        elif len(value) > FIELD_LIMIT:
            errors[key] = f"Must be at most {FIELD_LIMIT} characters"
    return errors

def load_profile():
    profile = dict(PROFILE_DEFAULTS)
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            profile.update(json.load(f))
    return profile

def save_profile(profile):
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
