from abc import ABC, abstractmethod

class BaseAIProvider(ABC):
    """Base strategy class for AI text generation."""
    
    @abstractmethod
    def generate(self, prompt: str, system_msg: str = "", max_tokens: int = 250) -> str:
        """Generate text given a prompt and optional system message."""
        pass