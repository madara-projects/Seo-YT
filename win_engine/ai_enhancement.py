"""AI Enhancement Module for YouTube Win-Engine using FREE Hugging Face models."""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from functools import lru_cache

# Optional imports - gracefully handle missing dependencies
try:
    from sentence_transformers import SentenceTransformer
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    from sklearn.metrics.pairwise import cosine_similarity
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    SentenceTransformer = None
    pipeline = None
    AutoTokenizer = None
    AutoModelForSequenceClassification = None
    cosine_similarity = None

logger = logging.getLogger(__name__)


class AIEnhancement:
    """AI-powered enhancements using free Hugging Face models."""

    def __init__(self):
        self.models_loaded = False
        self.sentence_model = None
        self.sentiment_classifier = None
        self.topic_classifier = None

        if AI_AVAILABLE:
            self._load_models()
        else:
            logger.warning("AI dependencies not available. Install with: pip install sentence-transformers transformers torch")

    def _load_models(self):
        """Load AI models (downloads on first use)."""
        try:
            logger.info("Loading AI models... (this may take a moment on first run)")

            # Sentence transformer for semantic similarity
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

            # Sentiment analysis for content quality
            self.sentiment_classifier = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                return_all_scores=True
            )

            # Zero-shot classification for topic analysis
            self.topic_classifier = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli"
            )

            self.models_loaded = True
            logger.info("AI models loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load AI models: {e}")
            self.models_loaded = False

    def is_available(self) -> bool:
        """Check if AI features are available."""
        return AI_AVAILABLE and self.models_loaded

    def analyze_content_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts (0-1 scale)."""
        if not self.is_available():
            return 0.0

        try:
            embeddings = self.sentence_model.encode([text1, text2])
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return float(similarity)
        except Exception as e:
            logger.error(f"Similarity analysis failed: {e}")
            return 0.0

    def score_content_quality(self, text: str) -> Dict[str, Any]:
        """AI-powered content quality analysis."""
        if not self.is_available():
            return {"quality_score": 5.0, "sentiment": "neutral", "confidence": 0.0}

        try:
            # Sentiment analysis
            sentiment_results = self.sentiment_classifier(text)
            if sentiment_results:
                # Get the highest scoring sentiment
                top_sentiment = max(sentiment_results[0], key=lambda x: x['score'])
                sentiment = top_sentiment['label'].lower()
                confidence = top_sentiment['score']
            else:
                sentiment = "neutral"
                confidence = 0.0

            # Quality scoring based on multiple factors
            quality_score = self._calculate_quality_score(text, sentiment, confidence)

            return {
                "quality_score": quality_score,
                "sentiment": sentiment,
                "confidence": confidence,
                "analysis": self._analyze_content_factors(text)
            }

        except Exception as e:
            logger.error(f"Quality scoring failed: {e}")
            return {"quality_score": 5.0, "sentiment": "neutral", "confidence": 0.0}

    def _calculate_quality_score(self, text: str, sentiment: str, confidence: float) -> float:
        """Calculate overall quality score (0-10 scale)."""
        score = 5.0  # Base score

        # Length factor (YouTube scripts should be substantial)
        word_count = len(text.split())
        if 50 <= word_count <= 2000:
            score += 1.0
        elif word_count < 50:
            score -= 1.0

        # Sentiment factor (engaging content tends to be positive)
        if sentiment in ['positive', 'joy', 'optimism']:
            score += 0.5
        elif sentiment in ['negative', 'anger', 'fear']:
            score -= 0.5

        # Confidence factor (AI certainty in analysis)
        score += confidence * 2.0  # 0-2 points based on confidence

        # Content structure (has questions, lists, etc.)
        if '?' in text:
            score += 0.5  # Engaging questions
        if any(char in text for char in ['•', '-', '1.', '2.']):
            score += 0.5  # Structured content

        return max(0.0, min(10.0, score))

    def _analyze_content_factors(self, text: str) -> Dict[str, Any]:
        """Analyze various content factors."""
        return {
            "word_count": len(text.split()),
            "sentence_count": len([s for s in text.split('.') if s.strip()]),
            "has_questions": '?' in text,
            "has_lists": any(char in text for char in ['•', '-', '1.', '2.']),
            "has_emojis": any(ord(char) > 127 for char in text),
            "avg_sentence_length": np.mean([len(s.split()) for s in text.split('.') if s.strip()]) if text else 0
        }

    def classify_content_topic(self, text: str, candidate_topics: Optional[List[str]] = None) -> Dict[str, Any]:
        """Classify content into topics using zero-shot classification."""
        if not self.is_available():
            return {"topic": "general", "confidence": 0.0}

        if candidate_topics is None:
            candidate_topics = [
                "Technology", "Education", "Entertainment", "Lifestyle",
                "Business", "Health", "Science", "Sports", "Travel", "Food"
            ]

        try:
            result = self.topic_classifier(text, candidate_topics, multi_label=False)
            return {
                "topic": result['labels'][0],
                "confidence": result['scores'][0],
                "all_scores": dict(zip(result['labels'], result['scores']))
            }
        except Exception as e:
            logger.error(f"Topic classification failed: {e}")
            return {"topic": "general", "confidence": 0.0}

    def find_similar_content(self, target_script: str, competitor_scripts: List[str], top_k: int = 3) -> List[Tuple[str, float]]:
        """Find most similar competitor content."""
        if not self.is_available():
            return []

        try:
            all_texts = [target_script] + competitor_scripts
            embeddings = self.sentence_model.encode(all_texts)

            target_embedding = embeddings[0]
            competitor_embeddings = embeddings[1:]

            similarities = cosine_similarity([target_embedding], competitor_embeddings)[0]

            # Get top similar content
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            results = [(competitor_scripts[i], similarities[i]) for i in top_indices]

            return results

        except Exception as e:
            logger.error(f"Similar content analysis failed: {e}")
            return []

    def generate_smart_insights(self, script: str, competitor_data: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate AI-powered insights for content optimization."""
        if not self.is_available():
            return {"insights": [], "recommendations": []}

        insights = []

        # Quality analysis
        quality = self.score_content_quality(script)
        if quality['quality_score'] < 6.0:
            insights.append({
                "type": "quality",
                "level": "warning",
                "message": f"Content quality score is {quality['quality_score']:.1f}/10. Consider adding more engaging elements."
            })

        # Topic analysis
        topic_info = self.classify_content_topic(script)
        insights.append({
            "type": "topic",
            "level": "info",
            "message": f"Content classified as '{topic_info['topic']}' topic with {topic_info['confidence']:.1f} confidence."
        })

        # Competitor analysis
        if competitor_data:
            similar_content = self.find_similar_content(script, competitor_data, top_k=2)
            if similar_content:
                max_similarity = max(sim for _, sim in similar_content)
                if max_similarity > 0.7:
                    insights.append({
                        "type": "competition",
                        "level": "warning",
                        "message": f"High similarity ({max_similarity:.2f}) with competitor content. Consider differentiation."
                    })

        # Sentiment analysis
        if quality['sentiment'] in ['negative', 'anger', 'fear']:
            insights.append({
                "type": "sentiment",
                "level": "warning",
                "message": f"Content sentiment is {quality['sentiment']}. Consider making it more positive and engaging."
            })

        return {
            "insights": insights,
            "quality_score": quality['quality_score'],
            "topic": topic_info['topic'],
            "sentiment": quality['sentiment']
        }


# Global AI enhancement instance
ai_enhancement = AIEnhancement()


def get_ai_insights(script: str, competitor_scripts: Optional[List[str]] = None) -> Dict[str, Any]:
    """Get AI-powered insights for a script."""
    return ai_enhancement.generate_smart_insights(script, competitor_scripts)


def analyze_content_quality_ai(script: str) -> Dict[str, Any]:
    """AI-powered content quality analysis."""
    return ai_enhancement.score_content_quality(script)


def find_content_similarity(script1: str, script2: str) -> float:
    """Calculate semantic similarity between two scripts."""
    return ai_enhancement.analyze_content_similarity(script1, script2)