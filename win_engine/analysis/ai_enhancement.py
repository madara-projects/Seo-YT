import logging
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer, util
    from transformers import pipeline
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logger.warning("AI libraries not installed. Run: pip install sentence-transformers transformers torch")

# Import Clean Engine Architecture
from win_engine.ai.provider_factory import ProviderFactory
from win_engine.engine.viral_package_engine import ViralPackageEngine

class LightweightAIEngine:
    """
    Clean Core Engine acting as a facade for the local fast NLP Models 
    and the newly refactored provider-based AI generation systems.
    """

    def __init__(self):
        if not AI_AVAILABLE:
            raise ImportError("Please install required AI libraries")

        logger.info("Loading Lightweight Local AI Models...")

        # Local models
        self.similarity_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.sentiment_classifier = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest"
        )

        logger.info("AI Models loaded successfully.")

    # ----------------------------
    # 🔍 SEMANTIC UNIQUENESS
    # ----------------------------

    def calculate_uniqueness(self, user_script: str, competitor_scripts: List[str]) -> float:
        if not competitor_scripts:
            return 1.0

        user_embedding = self.similarity_model.encode(user_script, convert_to_tensor=True)
        competitor_embeddings = self.similarity_model.encode(competitor_scripts, convert_to_tensor=True)

        cosine_scores = util.cos_sim(user_embedding, competitor_embeddings)[0]
        max_similarity = float(cosine_scores.max())

        uniqueness_score = max(0.0, 1.0 - max_similarity)
        return round(uniqueness_score, 2)

    # ----------------------------
    # ❤️ EMOTIONAL ANALYSIS
    # ----------------------------
    def score_emotional_hook(self, text: str) -> Dict[str, Any]:
        result = self.sentiment_classifier(text[:512])[0]
        return {
            "primary_emotion": result["label"],
            "confidence_score": round(result["score"], 2)
        }

    # ----------------------------
    # 👑 MASTER GENERATORS (Delegated to Engines)
    # ----------------------------
    def generate_viral_package(self, script_summary: str) -> Dict[str, Any]:
        mode = os.environ.get("WIN_ENGINE_AI_MODE", "Auto (Recommended)")
        provider = ProviderFactory.get_provider(mode)
        engine = ViralPackageEngine(provider)
        return engine.generate(script_summary)

    def generate_title(self, script_summary: str) -> str:
        pkg = self.generate_viral_package(script_summary)
        return pkg.get("title", "How to Learn Faster (Step-by-Step Guide)")

# ----------------------------
# 🔁 SINGLETON INSTANCE
# ----------------------------
_engine_instance = None

def get_ai_engine() -> LightweightAIEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LightweightAIEngine()
    return _engine_instance
