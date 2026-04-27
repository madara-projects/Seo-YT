import requests
import logging
from .base_provider import BaseAIProvider
from win_engine.utils.retry import retry

logger = logging.getLogger(__name__)

class OllamaProvider(BaseAIProvider):
    def __init__(self, timeout: int = 15):
        self.url = "http://localhost:11434/api/generate"
        self.timeout = timeout

    def generate(self, prompt: str, system_msg: str = "", max_tokens: int = 250) -> str:
        def _call_api():
            full_prompt = f"{system_msg}\n\n{prompt}" if system_msg else prompt
            payload = {
                "model": "mistral",
                "prompt": full_prompt,
                "stream": False
            }
            res = requests.post(self.url, json=payload, timeout=self.timeout)
            return res.json().get("response", "").strip()

        return retry(_call_api, retries=2, delay=1)