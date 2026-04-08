from __future__ import annotations

from typing import Any


def build_language_strategy(script: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Simple language and localization baseline for Phase 7."""

    context = context or {}
    lowered = script.lower()
    hindi_markers = [" hai ", " kya ", " kaise ", " aur ", " karna ", " nahi ", " kyun "]
    spanish_markers = [" como ", " porque ", " canal ", " crecer ", " video "]
    tanglish_markers = [" da ", " pa ", " illa ", " macha ", " semma ", " vera level ", " podu ", " ah "]
    non_ascii_count = sum(1 for char in script if ord(char) > 127)
    normalized = f" {lowered} "
    selected_language = str(context.get("language", "")).strip().lower()
    region = str(context.get("region", "")).strip() or "Global"
    audience_type = str(context.get("audience_type", "")).strip() or "General"
    tanglish_score = sum(normalized.count(token) for token in tanglish_markers)

    if selected_language in {"english", "tamil"}:
        primary_language = selected_language
    elif tanglish_score >= 2 and non_ascii_count == 0:
        primary_language = "tanglish"
    elif non_ascii_count > 3 or sum(normalized.count(token) for token in hindi_markers) >= 3:
        primary_language = "hinglish_or_hindi"
    elif sum(normalized.count(token) for token in spanish_markers) >= 3:
        primary_language = "spanish_like"
    else:
        primary_language = "english"

    localization_tip = {
        "english": "Keep titles compact and searchable, then test localized subtitles later.",
        "tamil": "Lean into native phrasing, spoken rhythm, and locally recognizable emotional hooks.",
        "tanglish": "Use clean bilingual phrasing, keep the hook easy to understand, and avoid overstuffing slang.",
        "hinglish_or_hindi": "Consider a bilingual title format and keep hook lines easy to subtitle.",
        "spanish_like": "Use native-language title variants and keep keywords idiomatic rather than translated literally.",
    }.get(primary_language, "Keep the packaging local to the audience you want to reach.")

    emotional_triggers = _emotional_triggers(primary_language)
    regional_bias = _regional_bias(region, audience_type)
    packaging_style = _packaging_style(primary_language, audience_type)

    return {
        "primary_language": primary_language,
        "multi_language_ready": primary_language != "english",
        "recommendation": localization_tip,
        "selected_region": region,
        "audience_type": audience_type,
        "tanglish_detected": primary_language == "tanglish",
        "regional_bias": regional_bias,
        "emotional_triggers": emotional_triggers,
        "packaging_style": packaging_style,
    }


def _regional_bias(region: str, audience_type: str) -> dict[str, Any]:
    lowered_region = region.lower()
    lowered_audience = audience_type.lower()

    market_tier = "global"
    if lowered_region in {"india", "tamil nadu", "sri lanka", "gulf"}:
        market_tier = "regional"

    return {
        "region": region,
        "audience_type": audience_type,
        "market_tier": market_tier,
        "competition_weight": "lighter" if lowered_audience in {"local", "diaspora"} else "standard",
        "discovery_hint": (
            "Favor local wording and cultural specificity."
            if market_tier == "regional"
            else "Favor broad, searchable phrasing."
        ),
    }


def _emotional_triggers(primary_language: str) -> list[str]:
    mapping = {
        "english": ["clarity", "curiosity", "specific payoff"],
        "tamil": ["emotion", "relatability", "dramatic payoff"],
        "tanglish": ["relatability", "spoken rhythm", "fast curiosity"],
        "hinglish_or_hindi": ["identity", "emotion", "clear result"],
        "spanish_like": ["emotion", "community", "specific outcome"],
    }
    return mapping.get(primary_language, ["clarity", "specific payoff"])


def _packaging_style(primary_language: str, audience_type: str) -> str:
    if primary_language in {"tamil", "tanglish"} and audience_type.lower() in {"local", "diaspora"}:
        return "bilingual_curiosity"
    if primary_language == "english":
        return "searchable_curiosity"
    return "localized_emotion"
