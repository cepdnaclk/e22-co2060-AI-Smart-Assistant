import requests
import logging
import json
import time

from src.settings import load_settings

logger = logging.getLogger(__name__)

class MistralClient:
    """
    Wrapper for interacting with a local Ollama model API.
    The URL, model, temperature and max tokens come from settings (config.json)
    unless passed in explicitly.
    """

    def __init__(self, base_url: str = None, model: str = None):
        settings = load_settings()
        model_settings = settings["model"]
        self.base_url = (base_url or model_settings["ollama_url"]).rstrip("/")
        if settings["general"].get("offline_mode"):
            self.base_url = "http://127.0.0.1:11434"
        self.model = model or model_settings["model"]
        self.temperature = model_settings["temperature"]
        self.max_tokens = model_settings["max_tokens"]

    def _options(self, max_tokens: int = None) -> dict:
        return {
            "temperature": self.temperature,
            "num_predict": max_tokens or self.max_tokens,
        }

    def generate(self, prompt: str, max_tokens: int = None) -> dict:
        """
        Send a prompt to the model and return the response.
        Handles Ollama's streaming NDJSON output.
        Retries on 500 errors (model loading).
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "options": self._options(max_tokens)
                    },
                    stream=True,
                    timeout=120
                )

                # Retry on 500 (Ollama still loading model)
                if response.status_code == 500 and attempt < max_retries - 1:
                    wait_time = 5 * (attempt + 1)
                    logger.warning(f"Ollama returned 500 (model loading?). Retrying in {wait_time}s... (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()

                full_text = ""
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line.decode("utf-8"))
                        if "response" in data:
                            full_text += data["response"]
                        if data.get("done"):
                            break

                logger.info("Mistral response received successfully.")
                return {"response": full_text}

            except requests.exceptions.Timeout:
                logger.error("Mistral request timed out.")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return {"error": "Request timed out"}

            except requests.exceptions.ConnectionError:
                logger.error("Could not connect to Mistral API. Make sure Ollama is running.")
                return {"error": "Connection error. Make sure Ollama is running."}

            except Exception as e:
                logger.exception("Unexpected error while calling Mistral.")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return {"error": str(e)}

        return {"error": "Failed after multiple retries"}

    def chat(self, messages: list[dict]) -> dict:
        """
        Chat-style interface with Mistral.
        messages = [{"role": "user", "content": "Hello!"}]
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "options": self._options()
                },
                stream=True,
                timeout=120
            )
            response.raise_for_status()

            full_text = ""
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode("utf-8"))
                    if "message" in data and "content" in data["message"]:
                        full_text += data["message"]["content"]
                    if data.get("done"):
                        break

            logger.info("Mistral chat response received successfully.")
            return {"response": full_text}

        except Exception as e:
            logger.exception("Error in Mistral chat call.")
            return {"error": str(e)}

    def list_models(self) -> dict:
        """
        List the models installed in Ollama.
        Returns {"models": ["mistral:latest", ...], "error": None} or {"models": [], "error": "..."}.
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            names = [m["name"] for m in response.json().get("models", []) if "name" in m]
            return {"models": sorted(names), "error": None}
        except requests.exceptions.ConnectionError:
            return {"models": [], "error": "Connection error. Make sure Ollama is running."}
        except Exception as e:
            return {"models": [], "error": str(e)}

    def ping(self) -> dict:
        """
        Check that Ollama is reachable and the selected model is installed.
        Returns {"ok": bool, "detail": str}.
        """
        result = self.list_models()
        if result["error"]:
            return {"ok": False, "detail": result["error"]}

        installed = result["models"]
        names = set(installed) | {name.split(":")[0] for name in installed}
        if self.model not in names:
            return {"ok": False, "detail": f"Ollama is running, but model '{self.model}' is not installed. Run: ollama pull {self.model}"}
        return {"ok": True, "detail": f"Connected to Ollama. Model '{self.model}' is ready."}