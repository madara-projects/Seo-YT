"""Offline regression coverage for creative direction and creator title styling."""
import json
from unittest.mock import patch

from win_engine.analysis.generation_quality import title_emojis
from win_engine.generation import flow_prompts as fp
from win_engine.generation.ai_shorts import creator_brief_for_quote
from win_engine.llm import gemini_client, seo_writer

QUOTE = "The best way to not get your heart broken is to pretend that you don't have one."
# What the director returns: its reading of the quote, three literal candidates and the chosen one.
DIRECTOR_REPLY = {
    "quote_meaning": "Someone hurt before now acts as if nothing touches them, so nothing can hurt them again.",
    "emotion": "Guarded, numb after heartbreak",
    "tone": "numb",
    "candidates": [
        "A lone figure seen from behind walks along an empty seawall at blue dusk.",
        "A figure sits alone at a bus stop at night as headlights pass.",
        "A figure stands at the end of a pier as grey waves roll in.",
    ],
    "scene": "A lone figure seen from behind walks slowly along an empty seawall at blue dusk, the sea dark and calm.",
    "why_it_fits": "Walking alone in the cold blue light reads at once as someone keeping the world at a distance.",
    "opening": "The figure walks slowly along the seawall as small waves roll in below.",
    "middle": "The wind moves their coat and hair as they keep walking.",
    "ending": "They walk on toward the fading horizon as the waves keep rolling.",
    "search_themes": ["heartbreak quotes", "sad love quotes", "#sadquotes", "emotional numbness", "Heartbreak Quotes"],
    "hashtag": "Heartbreak",
    "emojis": ["🖤", "💔"],
}
# What the plan carries: the six text fields and the three typed ones, validated.
DIRECTION = {
    **{key: DIRECTOR_REPLY[key] for key in ("quote_meaning", "scene", "why_it_fits", "opening", "middle", "ending")},
    "emotion": "guarded, numb after heartbreak",
    "tone": "numb",
    "search_themes": ["heartbreak quotes", "sad love quotes", "emotional numbness"],
    "hashtag": "#heartbreak",
    "emojis": ["🖤", "💔"],
}
TRACE = {"status": "gemini_success", "attempts": 1, "model": "mock"}
UNDERSTANDING_KEYS = ("quote_meaning", "emotion", "tone", "search_themes", "hashtag", "emojis")


def scene_reply():
    prompt = (
        "Wide shot, slow tracking move on a 35mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
        "A lone figure in a dark coat, seen from behind and small in the lower third, walks slowly along an empty "
        "seawall at blue dusk. In the opening small waves roll in below; in the middle the wind moves their coat; in "
        "the ending they keep walking toward the fading horizon. Cool blue-teal tones; the upper-middle stays dark, "
        "clear and uncluttered for text added later. "
        + fp.NEGATIVE_PROMPT + " Ambient noise: wind and slow waves. " + fp.NO_VOICE_SENTENCE
    )
    return json.dumps({"shots": [{"part": 1, "prompt": prompt}], "audio_description": "wind and slow waves",
                       "mood": {"feeling": "love unreturned", "keywords": ["seawall"], "pace": "slow"}})


def test_director_runs_before_writer_and_direction_is_saved():
    with patch.object(gemini_client, "is_available", return_value=True), patch.object(
        gemini_client, "generate_with_diagnostics",
        side_effect=[(json.dumps(DIRECTOR_REPLY), TRACE), (scene_reply(), TRACE)],
    ) as generate:
        plan = fp.plan_flow_shots(QUOTE, parts=1, creative_direction=True)
    assert generate.call_count == 2
    writer_prompt = generate.call_args_list[1].args[0]
    assert DIRECTION["scene"] in writer_prompt
    # The writer is told the tone's light; the search themes are the package's business, not the camera's.
    assert "the quote's tone is numb" in writer_prompt and "heartbreak quotes" not in writer_prompt
    # The local keyword guess ("love unreturned", from "heart") no longer reaches the writer.
    assert "Feeling read locally" not in writer_prompt and "love unreturned" not in writer_prompt
    assert plan["creative_direction"] == DIRECTION
    assert list(plan["creative_direction"]) == [*DIRECTION]
    # The reading of the quote in one place, the same values as the direction's.
    assert plan["quote_understanding"] == {key: DIRECTION[key] for key in UNDERSTANDING_KEYS}
    assert plan["generation_source"] == "gemini"
    assert plan["provider"]["repair_attempted"] is False
    assert plan["checks"]["passed"] is True
    assert "in the middle the wind moves their coat" in plan["shots"][0]["prompt"]
    # The mood follows the director's reading, not the writer's label or the keyword guess.
    assert plan["mood"]["feeling"] == "guarded, numb after heartbreak"
    assert plan["mood"]["keywords"][:3] == ["numb", "guarded", "numb after heartbreak"]


def test_a_symbolic_director_scene_is_dropped_and_the_writer_chooses_from_the_literal_candidates():
    # The creator's case: "pretend you don't have a heart" became a pocket watch wound in wool.
    symbolic = {
        **DIRECTOR_REPLY,
        "scene": "A gloved hand holding a vintage pocket watch; thick wool fabric is wound around the ticking object.",
        "opening": "The gloved hand holds the pocket watch as the wool is wound around it.",
        "middle": "The wool covers the watch face.",
        "ending": "All movement and sound cease as the bundle rests completely still.",
    }
    with patch.object(gemini_client, "is_available", return_value=True), patch.object(
        gemini_client, "generate_with_diagnostics",
        side_effect=[(json.dumps(symbolic), TRACE), (scene_reply(), TRACE)],
    ) as generate:
        plan = fp.plan_flow_shots(QUOTE, parts=1, creative_direction=True)
    assert generate.call_count == 2
    writer_prompt = generate.call_args_list[1].args[0]
    assert "pocket watch" not in writer_prompt and "wool" not in writer_prompt
    assert "empty seawall at blue dusk" in writer_prompt
    assert "Someone hurt before now acts as if nothing touches them" in writer_prompt
    # The reading is never dropped: the director's next literal candidate becomes the scene.
    assert plan["creative_direction"]["scene"] == DIRECTOR_REPLY["candidates"][0]
    assert any("Creative direction chose a symbol (a watch, an object being wrapped or bound)" in warning
               and "next candidate" in warning for warning in plan["checks"]["warnings"])
    assert plan["generation_source"] == "gemini" and plan["checks"]["passed"] is True
    # The scene was thrown away; the reading of the quote was not.
    assert plan["quote_understanding"] == {key: DIRECTION[key] for key in UNDERSTANDING_KEYS}
    assert plan["mood"]["feeling"] == "guarded, numb after heartbreak"


def test_malformed_director_output_does_not_break_prompt_generation():
    with patch.object(gemini_client, "is_available", return_value=True), patch.object(
        gemini_client, "generate_with_diagnostics",
        side_effect=[('{"scene": ["wrong shape"]}', TRACE), (scene_reply(), TRACE)],
    ):
        plan = fp.plan_flow_shots(QUOTE, parts=1, creative_direction=True)
    assert "creative_direction" not in plan and "quote_understanding" not in plan
    assert plan["generation_source"] == "gemini"
    # The reason is named from field names only, never from generated text.
    assert any(
        warning.startswith("Creative direction was unavailable (missing quote_meaning, scene, why_it_fits")
        for warning in plan["checks"]["warnings"]
    )


def test_a_director_cut_off_by_the_provider_says_why_without_generated_text():
    truncated = {"status": "gemini_truncated", "failure_category": "output_token_limit", "attempts": 2}
    with patch.object(gemini_client, "is_available", return_value=True), patch.object(
        gemini_client, "generate_with_diagnostics", side_effect=[("", truncated), (scene_reply(), TRACE)],
    ):
        plan = fp.plan_flow_shots(QUOTE, parts=1, creative_direction=True)
    assert "Creative direction was unavailable (output_token_limit); the prompt writer interpreted the quote directly." \
        in plan["checks"]["warnings"]


def test_trimming_keeps_the_middle_and_ending_not_decorative_details():
    prompt = json.loads(scene_reply())["shots"][0]["prompt"] + " Beautiful cinematic gentle muted atmospheric lighting." * 40
    trimmed = fp.trim_prompt(prompt, part=1)
    assert "in the middle the wind moves their coat" in trimmed
    assert "in the ending they keep walking" in trimmed
    assert fp.word_count(trimmed) <= fp.MAX_PROMPT_WORDS


def test_ai_shorts_titles_get_style_before_quality_gate():
    brief = creator_brief_for_quote(QUOTE, {"total_seconds": 8}, language="english", region="global")
    cleaned = seo_writer._sanitize_generated_package({
        "title": "Pretending you don't have a heart",
        "variants": ["Pretending you don't have a heart", "Hiding your heart to avoid being hurt 🥀 #shorts"],
        "description": QUOTE,
    }, QUOTE, brief)
    for title in [cleaned["title"], *cleaned["variants"]]:
        assert title.endswith("#shorts")
        assert title.lower().count("#shorts") == 1
        assert len(title) <= 100
        assert len(title_emojis(title)) == 1
    # Emotional denial, not heartbreak felt: the tone's emoji, never 💔 for the word "heart".
    assert "🖤" in cleaned["title"]


def test_normal_creator_titles_are_not_forced_to_use_ai_shorts_style():
    cleaned = seo_writer._sanitize_generated_package({"title": "Protect your heart", "description": QUOTE}, QUOTE)
    assert "#shorts" not in cleaned["title"]


def test_writer_receives_creator_style_and_source_grounded_tag_instructions():
    brief = creator_brief_for_quote(QUOTE, {"total_seconds": 8}, language="english", region="global")
    prompt = seo_writer._build_user_prompt(
        QUOTE, competitor_block="", language="english", region="global", audience_type="general", creator_brief=brief,
    )
    assert "Creator preference for this AI Short" in prompt
    assert "never pad with unrelated trending tags" in prompt
