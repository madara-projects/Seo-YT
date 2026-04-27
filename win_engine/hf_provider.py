import os
import requests
import logging
from .base_provider import BaseAIProvider
from win_engine.utils.retry import retry

logger = logging.getLogger(__name__)

class HFProvider(BaseAIProvider):
    def __init__(self, timeout: int = 15):
        self.hf_token = os.environ.get("HF_TOKEN")
        self.timeout = timeout
        self.models = ["gpt2", "distilgpt2"]

    def generate(self, prompt: str, system_msg: str = "", max_tokens: int = 250) -> str:
        if not self.hf_token:
            return ""

        headers = {"Authorization": f"Bearer {self.hf_token}"}
        full_prompt = f"{system_msg}\n\n{prompt}" if system_msg else prompt
        payload = {"inputs": full_prompt, "parameters": {"max_new_tokens": max_tokens, "temperature": 0.7}}

        def _call_api(model: str):
            url = f"https://api-inference.huggingface.co/models/{model}"
            res = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            return res.json()[0].get("generated_text", "").strip()

        for model in self.models:
            res = retry(lambda: _call_api(model), retries=2, delay=2)
            if res: return res
            
        return ""