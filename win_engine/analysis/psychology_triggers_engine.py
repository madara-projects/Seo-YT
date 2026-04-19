"""
Phase 13.3: Psychological Triggers Analysis Engine
Analyzes title/description for psychological hook effectiveness
Scores curiosity gaps, emotional triggers, urgency signals, and social proof
"""

from __future__ import annotations

from typing import Any


class PsychologyTriggersAnalyzer:
    """Advanced analysis of psychological triggers in YouTube content."""

    # Psychological trigger patterns
    CURIOSITY_TRIGGERS = [
        r"\bwon't\b", r"\bdon't\b", r"\bcan't\b", r"\bfinally\b",
        r"\brevealed\b", r"\bsecret\b", r"\bhidden\b", r"\bdiscovered\b",
        r"\btruth\b", r"\bsurprised\b", r"\bunbelievable\b", r"\bshocking\b",
        r"\bincredible\b", r"\bamazing\b", r"\binsane\b", r"\bcrazy\b",
    ]
    
    URGENCY_TRIGGERS = [
        r"\blimited\b", r"\bonly\b", r"\btonight\b", r"\btoday\b",
        r"\b(this\s+)?week\b", r"\bnow\b", r"\blast\s+chance\b",
        r"\bdeadline\b", r"\bbefore\b", r"\bexpires\b", r"\bending\b",
    ]
    
    EMOTIONAL_TRIGGERS = [
        r"\blove\b", r"\bhate\b", r"\bfear\b", r"\banger\b",
        r"\bawful\b", r"\bterrible\b", r"\bdevastated\b", r"\bso\s+happy\b",
        r"\bheartbreaking\b", r"\binspiring\b", r"\bemotional\b",
    ]
    
    SOCIAL_PROOF_TRIGGERS = [
        r"\bevery\w+\b", r"\bmillions?\s+(people|users|viewers)", r"\btrending\b",
        r"\b#\d+\b", r"\bvirall?", r"\bbillion\b", r"\bmassive\b",
        r"\bfamous\b", r"\bceleb\w+\b", r"\binfluencer\b",
    ]
    
    POWER_WORDS = [
        "revealed", "secret", "proven", "guaranteed", "ultimate", "insane",
        "shocking", "incredible", "amazing", "unbelievable", "jaw-dropping",
        "game-changing", "breakthrough", "never-before-seen", "exclusive",
    ]

    def __init__(self):
        """Initialize the psychology analyzer."""
        pass

    def analyze_title_psychology(self, title: str) -> dict[str, Any]:
        """
        Analyze psychological triggers in title.
        
        Returns scores for:
        - Curiosity gap strength
        - Urgency signals
        - Emotional resonance
        - Social proof indicators
        """
        
        title_lower = title.lower()
        
        curiosity_score = self._score_triggers(title_lower, self.CURIOSITY_TRIGGERS)
        urgency_score = self._score_triggers(title_lower, self.URGENCY_TRIGGERS)
        emotional_score = self._score_triggers(title_lower, self.EMOTIONAL_TRIGGERS)
        social_proof_score = self._score_triggers(title_lower, self.SOCIAL_PROOF_TRIGGERS)
        
        # Inject Local AI emotional scoring
        try:
            from win_engine.analysis.ai_enhancement import get_ai_engine
            engine = get_ai_engine()
            ai_emotion = engine.score_emotional_hook(title)
            if ai_emotion.get("primary_emotion") in ["positive", "negative"]:
                # Boost emotional score if AI detects strong sentiment
                emotional_score = max(emotional_score, ai_emotion.get("confidence_score", 0.0))
        except Exception:
            pass

        power_word_count = sum(1 for word in self.POWER_WORDS if word in title_lower)
        
        # Calculate composite psychological strength (0-100)
        composite = (
            (curiosity_score * 0.35) +
            (urgency_score * 0.25) +
            (emotional_score * 0.25) +
            (social_proof_score * 0.15)
        ) * 100
        
        return {
            "composite_score": round(composite, 1),
            "strength_level": self._score_to_level(composite),
            "components": {
                "curiosity_gap": {
                    "score": round(curiosity_score * 100, 1),
                    "level": self._score_to_level(curiosity_score),
                    "interpretation": self._curiosity_interpretation(curiosity_score),
                },
                "urgency_signals": {
                    "score": round(urgency_score * 100, 1),
                    "level": self._score_to_level(urgency_score),
                    "interpretation": self._urgency_interpretation(urgency_score),
                },
                "emotional_resonance": {
                    "score": round(emotional_score * 100, 1),
                    "level": self._score_to_level(emotional_score),
                    "interpretation": self._emotional_interpretation(emotional_score),
                },
                "social_proof": {
                    "score": round(social_proof_score * 100, 1),
                    "level": self._score_to_level(social_proof_score),
                    "interpretation": self._social_proof_interpretation(social_proof_score),
                },
            },
            "power_words_detected": power_word_count,
            "psychological_weight": self._calculate_psychological_weight(
                title_lower, curiosity_score, urgency_score, emotional_score
            ),
            "recommendations": self._generate_psychology_recommendations(
                title, curiosity_score, urgency_score, emotional_score, social_proof_score
            ),
        }

    def analyze_description_psychology(self, description: str, primary_topic: str = "") -> dict[str, Any]:
        """
        Analyze psychological triggers in description.
        Focus on hook quality and call-to-action effectiveness.
        """
        
        desc_lower = description.lower()
        first_100_chars = description[:100].lower()
        
        # Analyze first line (hook)
        hook_strength = self._analyze_hook(first_100_chars)
        
        # Count CTAs
        cta_count = self._count_ctas(desc_lower)
        
        # Overall description psychology
        curiosity_score = self._score_triggers(desc_lower, self.CURIOSITY_TRIGGERS)
        urgency_score = self._score_triggers(desc_lower, self.URGENCY_TRIGGERS)
        emotional_score = self._score_triggers(desc_lower, self.EMOTIONAL_TRIGGERS)
        
        return {
            "hook_quality": {
                "score": round(hook_strength * 100, 1),
                "strength": self._score_to_level(hook_strength),
                "feedback": self._hook_feedback(first_100_chars, hook_strength),
            },
            "call_to_action": {
                "count": cta_count,
                "effectiveness": "strong" if cta_count >= 2 else "weak" if cta_count == 0 else "moderate",
            },
            "psychology_profile": {
                "curiosity": round(curiosity_score * 100, 1),
                "urgency": round(urgency_score * 100, 1),
                "emotion": round(emotional_score * 100, 1),
            },
            "engagement_potential": self._estimate_engagement_potential(
                hook_strength, cta_count, curiosity_score, urgency_score
            ),
        }

    def _score_triggers(self, text: str, trigger_list: list[str]) -> float:
        """Score text against trigger patterns (0-1)."""
        
        import re
        
        matches = 0
        for trigger in trigger_list:
            if re.search(trigger, text):
                matches += 1
        
        # Normalize to 0-1 with diminishing returns
        score = min(matches / len(trigger_list), 1.0)
        return min(score, 1.0)

    def _score_to_level(self, score: float) -> str:
        """Convert numeric score to interpretable level."""
        
        if score >= 0.8:
            return "EXCELLENT"
        elif score >= 0.6:
            return "STRONG"
        elif score >= 0.4:
            return "MODERATE"
        elif score >= 0.2:
            return "WEAK"
        else:
            return "MINIMAL"

    def _curiosity_interpretation(self, score: float) -> str:
        """Interpret curiosity gap score."""
        
        if score >= 0.8:
            return "Strong curiosity gap. Viewers will want to click to learn more."
        elif score >= 0.6:
            return "Good curiosity trigger. Compelling enough for most audiences."
        elif score >= 0.4:
            return "Moderate curiosity. Consider adding more 'you won't believe' or 'revealed' angles."
        else:
            return "Limited curiosity hook. Your title is too literal. Add mystery or intrigue."

    def _urgency_interpretation(self, score: float) -> str:
        """Interpret urgency signals score."""
        
        if score >= 0.6:
            return "Strong urgency signals will push viewers to click immediately."
        elif score >= 0.4:
            return "Moderate urgency. Some FOMO present but could be stronger."
        else:
            return "No urgency signals. Add timely words or scarcity language for FOMO."

    def _emotional_interpretation(self, score: float) -> str:
        """Interpret emotional resonance score."""
        
        if score >= 0.6:
            return "Strong emotional appeal. Viewers will feel compelled by your promise."
        elif score >= 0.3:
            return "Moderate emotional tone. Could benefit from stronger feeling words."
        else:
            return "Neutral tone. Add emotional language to resonate with viewers."

    def _social_proof_interpretation(self, score: float) -> str:
        """Interpret social proof indicators."""
        
        if score >= 0.5:
            return "Social proof present. Leverages popularity/trends effectively."
        else:
            return "No social proof. Consider mentioning viral trends or popularity."

    def _calculate_psychological_weight(
        self,
        title: str,
        curiosity: float,
        urgency: float,
        emotion: float
    ) -> str:
        """Determine overall psychological weight of title."""
        
        weight = (curiosity * 0.4) + (urgency * 0.3) + (emotion * 0.3)
        
        if weight >= 0.7:
            return "high_impact"
        elif weight >= 0.5:
            return "moderate_impact"
        else:
            return "low_impact"

    def _generate_psychology_recommendations(
        self,
        title: str,
        curiosity: float,
        urgency: float,
        emotion: float,
        social_proof: float,
    ) -> list[dict[str, str]]:
        """Generate specific recommendations to improve title psychology."""
        
        recommendations = []
        
        if curiosity < 0.5:
            recommendations.append({
                "area": "Curiosity Gap",
                "issue": "Title doesn't create enough intrigue",
                "suggestion": "Add words like 'revealed', 'secret', 'shocking', 'you won't believe'",
                "example": f"Try: 'This {title.split()[-1]} Secret Will Shock You' or '{title} - Finally Revealed'",
            })
        
        if urgency < 0.4 and curiosity >= 0.5:
            recommendations.append({
                "area": "Urgency",
                "issue": "No FOMO or time-sensitive language",
                "suggestion": "Add urgency words: 'limited', 'only', 'this week', 'before it's too late'",
                "example": f"Try: '{title} - This Week Only' or '{title} - Last Chance'",
            })
        
        if emotion < 0.4 and curiosity >= 0.4:
            recommendations.append({
                "area": "Emotional Appeal",
                "issue": "Title feels too neutral/informational",
                "suggestion": "Add emotional language: 'heartbreaking', 'inspiring', 'insane', 'unbelievable'",
                "example": f"Try: '{title} - This Is Unbelievable' or 'My {title} Story (emotional)'",
            })
        
        if social_proof < 0.3:
            recommendations.append({
                "area": "Social Proof",
                "issue": "Not leveraging trends or popularity signals",
                "suggestion": "Mention trending status or popularity: 'trending', 'viral', 'millions watching'",
                "example": f"Try: '{title} (Trending on YouTube)' or 'Why Everyone Is Watching This'",
            })
        
        if len(recommendations) == 0:
            recommendations.append({
                "area": "Optimization",
                "issue": "Title is strong, but could be enhanced",
                "suggestion": "Add 2-3 psychological triggers for maximum impact",
                "example": "Test current version, then A/B test with added urgency or curiosity",
            })
        
        return recommendations

    def _analyze_hook(self, first_100: str) -> float:
        """Analyze strength of description hook (first 100 chars)."""
        
        import re
        
        # Check for hook patterns
        score = 0.3  # Base score
        
        # Question hooks = strong
        if "?" in first_100:
            score += 0.2
        
        # Imperative hooks = strong
        if re.search(r"^(watch|click|discover|learn|find)", first_100):
            score += 0.2
        
        # Curiosity words = strong
        if any(word in first_100 for word in ["reveal", "secret", "discover", "learn", "know"]):
            score += 0.2
        
        # Emotion words = good
        if any(word in first_100 for word in ["love", "amazing", "incredible", "shocking"]):
            score += 0.1
        
        return min(score, 1.0)

    def _count_ctas(self, text: str) -> int:
        """Count explicit calls-to-action in description."""
        
        import re
        
        cta_patterns = [
            r"subscribe", r"click", r"watch", r"check out",
            r"visit", r"join", r"download", r"like", r"comment",
        ]
        
        count = 0
        for pattern in cta_patterns:
            if re.search(pattern, text):
                count += 1
        
        return count

    def _hook_feedback(self, first_100: str, strength: float) -> str:
        """Generate feedback on description hook."""
        
        if strength >= 0.7:
            return "Excellent hook! Viewers will want to read the full description."
        elif strength >= 0.5:
            return "Good hook. Clear what they'll get from watching."
        elif strength >= 0.3:
            return "Decent hook. Could be more compelling."
        else:
            return "Weak hook. Start with a question or curiosity word to grab attention."

    def _estimate_engagement_potential(
        self,
        hook: float,
        cta_count: int,
        curiosity: float,
        urgency: float,
    ) -> str:
        """Estimate engagement potential from description elements."""
        
        score = (hook * 0.3) + (min(cta_count / 3, 1) * 0.2) + (curiosity * 0.25) + (urgency * 0.25)
        
        if score >= 0.7:
            return "High potential"
        elif score >= 0.5:
            return "Moderate potential"
        else:
            return "Needs improvement"


def analyze_content_psychology(
    title: str,
    description: str = "",
    primary_topic: str = "",
) -> dict[str, Any]:
    """
    Standalone function to analyze psychological triggers in content.
    
    Args:
        title: YouTube video title
        description: Video description (optional)
        primary_topic: Main topic for context (optional)
    
    Returns:
        Comprehensive psychology analysis with recommendations
    """
    
    analyzer = PsychologyTriggersAnalyzer()
    
    result = {
        "title_analysis": analyzer.analyze_title_psychology(title),
    }
    
    if description:
        result["description_analysis"] = analyzer.analyze_description_psychology(description, primary_topic)
    
    return result
