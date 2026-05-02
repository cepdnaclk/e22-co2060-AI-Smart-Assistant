import requests
import logging
import json
import time

logger = logging.getLogger(__name__)

class MistralClient:
    """
    Wrapper for interacting with a local Mistral model API.
    Assumes Ollama is running at http://localhost:11434.
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self.model = "mistral"

    def generate(self, prompt: str, max_tokens: int = 256) -> dict:
        """
        Send a prompt to the Mistral model and return the response.
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
                        "options": {"num_predict": max_tokens}
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
                    "messages": messages
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