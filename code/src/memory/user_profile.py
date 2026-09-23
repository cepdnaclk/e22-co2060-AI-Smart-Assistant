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

def load_profile():
    profile = dict(PROFILE_DEFAULTS)
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            profile.update(json.load(f))
    return profile

def save_profile(profile):
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
