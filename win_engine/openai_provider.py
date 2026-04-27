import os
import requests
import logging
from .base_provider import BaseAIProvider
from win_engine.utils.retry import retry

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseAIProvider):
    def __init__(self, timeout: int = 15):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.timeout = timeout
        self.url = "https://api.openai.com/v1/chat/completions"

    def generate(self, prompt: str, system_msg: str = "You are a YouTube growth expert.", max_tokens: int = 250) -> str:
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not found. OpenAI generation disabled.")
            return ""

        def _call_api():
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": max_tokens
            }
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            res = requests.post(self.url, headers=headers, json=payload, timeout=self.timeout)
            return res.json()["choices"][0]["message"]["content"].strip()

        return retry(_call_api, retries=2, delay=1)