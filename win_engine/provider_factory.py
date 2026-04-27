import logging
from .base_provider import BaseAIProvider
from .openai_provider import OpenAIProvider
from .ollama_provider import OllamaProvider
from .hf_provider import HFProvider

logger = logging.getLogger(__name__)

class ChainedProvider(BaseAIProvider):
    """Master fallback strategy: Ollama -> OpenAI -> HuggingFace"""
    def __init__(self):
        self.providers = [OllamaProvider(), OpenAIProvider(), HFProvider()]

    def generate(self, prompt: str, system_msg: str = "", max_tokens: int = 250) -> str:
        for provider in self.providers:
            res = provider.generate(prompt, system_msg, max_tokens)
            if res: return res
        return ""

class ProviderFactory:
    @staticmethod
    def get_provider(mode: str) -> BaseAIProvider:
        if mode == "Local AI (Ollama)":
            return OllamaProvider()
        elif mode == "Cloud AI (OpenAI)":
            return OpenAIProvider()
        else:
            return ChainedProvider()