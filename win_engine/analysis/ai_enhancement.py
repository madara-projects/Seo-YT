import logging
import os
import requests
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer, util
    from transformers import pipeline
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logger.warning("AI libraries not installed. Run: pip install sentence-transformers transformers torch")

class LightweightAIEngine:
    """
    A hybrid free AI engine.
    1. Local MiniLM/RoBERTa for CPU-friendly text scoring (~600MB).
    2. Hugging Face Serverless API for LLM title generation (Zero local storage).
    """

    def __init__(self):
        if not AI_AVAILABLE:
            raise ImportError("Please install the required AI libraries.")
        
        logger.info("Loading Lightweight Local AI Models...")
        
        # 1. MiniLM: ~80MB model, incredibly fast for semantic comparison
        self.similarity_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # 2. RoBERTa: ~500MB model for sentiment/emotional impact analysis
        self.sentiment_classifier = pipeline(
            "sentiment-analysis", 
            model="cardiffnlp/twitter-roberta-base-sentiment-latest"
        )
        logger.info("AI Models loaded successfully.")
        
        # 3. Cloud generation API configuration
        self.hf_token = os.environ.get("HF_TOKEN")
        if not self.hf_token:
            logger.info("HF_TOKEN not found in environment. Cloud text generation will be disabled.")
        self.generation_api_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"

    def calculate_uniqueness(self, user_script: str, competitor_scripts: List[str]) -> float:
        """
        Compares the user's script against competitors.
        Returns a score (0.0 to 1.0) representing how unique the script is.
        Lower similarity = Higher uniqueness.
        """
        if not competitor_scripts:
            return 1.0
            
        user_embedding = self.similarity_model.encode(user_script, convert_to_tensor=True)
        competitor_embeddings = self.similarity_model.encode(competitor_scripts, convert_to_tensor=True)
        
        # Calculate cosine similarities
        cosine_scores = util.cos_sim(user_embedding, competitor_embeddings)[0]
        
        # Get the highest similarity (closest competitor)
        max_similarity = float(cosine_scores.max())
        
        # Uniqueness is the inverse of the highest similarity
        uniqueness_score = max(0.0, 1.0 - max_similarity)
        return round(uniqueness_score, 2)

    def score_emotional_hook(self, text: str) -> Dict[str, Any]:
        """
        Analyzes the emotional impact of a title or hook.
        """
        result = self.sentiment_classifier(text[:512])[0]  # Analyze up to 512 chars
        return {
            "primary_emotion": result["label"],
            "confidence_score": round(result["score"], 2)
        }

    def generate_cloud_title(self, script_summary: str) -> str:
        """
        Calls the Hugging Face Serverless API to generate highly engaging text.
        It is free, requires no local GPU, and takes zero disk space.
        """
        if not self.hf_token:
            return ""
            
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        # Using prompt formatting specific to Instruction-tuned models like Mistral
        prompt = f"<s>[INST] You are an expert YouTube title creator. Generate ONE highly clickable, viral YouTube title (max 60 characters) for this video script. Do not include quotes or hashtags. Script: {script_summary[:1000]} [/INST]"
        
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 30, "temperature": 0.7, "return_full_text": False}
        }
        
        try:
            response = requests.post(self.generation_api_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            if isinstance(result, list) and "generated_text" in result[0]:
                # Clean up the output to prevent random LLM formatting noise
                title = result[0]["generated_text"].strip().strip('"\'')
                return title
        except Exception as e:
            logger.error(f"Cloud generation failed: {e}")
            
        return ""

# Singleton instance to prevent reloading models on every call
_engine_instance = None

def get_ai_engine() -> LightweightAIEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LightweightAIEngine()
    return _engine_instance
