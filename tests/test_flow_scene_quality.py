"""The Flow planner's scene checks: stillness, motion, symbols, crowds, the subject, light per tone, Part 2+.

Offline: Gemini is mocked at the client boundary, so no call leaves the process.
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch

import pytest

from win_engine.generation import flow_prompts as fp
from win_engine.llm import gemini_client

HEART = "The best way to not get your heart broken is to pretend that you don't have one."
PROUD = "Be proud of how hard you are trying."
# Its own words read hopeful (not one of the tones the quote's words override), so the director's tone stands.
HOPEFUL = "Every ending is a new beginning in disguise."
TRACE = {"status": "gemini_success", "attempts": 1, "retries": 0, "model": "gemini-test", "failure_category": None}
CLOSING = f"{fp.NEGATIVE_PROMPT} Ambient noise: wind and slow waves. {fp.NO_VOICE_SENTENCE}"
WALK = (
    "Wide shot, slow tracking move on a 35mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
    "A lone figure in a dark coat, seen from behind and small in the lower third, walks slowly along an empty seawall "
    "{light}. In the opening small waves roll in below; in the middle the wind moves their coat; in the ending they "
    "keep walking toward the horizon. Cinematic natural light; the upper-middle stays calm, uncluttered and in soft "
    "focus for text added later. "
)
NIGHT_WALK = WALK.format(light="at night under orange streetlights") + CLOSING
SUNRISE_WALK = WALK.format(light="at sunrise in warm golden light") + CLOSING
# The creator's example, as a writer would have put it into a prompt.
POCKET_WATCH = (
    "Close shot, slow push-in on a 50mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
    "A gloved hand holding a vintage pocket watch in the lower third; thick wool fabric is wound around the ticking "
    "object. In the ending, all movement and sound cease as the bundle rests completely still. Cinematic natural "
    "light, muted tones; the upper-middle stays calm for text added later. " + CLOSING
)


class Answers:
    """Gemini, mocked: answers with these replies in turn and records each prompt."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def __call__(self, prompt, system="", **kwargs):
        self.prompts.append(prompt)
        assert self.replies, "more Gemini calls than replies were planned"
        return self.replies.pop(0), dict(TRACE)


def plan_with(*replies: str, quote: str = HEART, parts: int = 1, director: bool = False, **kwargs):
    answers = Answers(*replies)
    with patch.multiple(gemini_client, is_available=lambda: True, generate_with_diagnostics=answers):
        plan = fp.plan_flow_shots(quote, parts=parts, creative_direction=director, **kwargs)
    return plan, answers


def writer_reply(*prompts: str, **extra) -> str:
    shots = [
        {"part": part, "title": f"Take {part}", "prompt": prompt,
         "continuity": None if part == 1 else "Same seawall, same camera; the light shifts."}
        for part, prompt in enumerate(prompts, start=1)
    ]
    return json.dumps({"mood": {"feeling": "guarded", "keywords": ["seawall"], "pace": "slow"},
                       "audio_description": "wind and slow waves", "shots": shots, **extra})


def director_reply(**overrides) -> str:
    data = {
        "quote_meaning": "Encouragement for someone exhausted by effort nobody sees.",
        "emotion": "tired but quietly proud",
        "tone": "hopeful",
        "candidates": ["A figure walks up a hill path at sunrise.", "A figure jogs along a beach at golden hour.",
                       "A figure stands on a rooftop at dawn as clouds drift."],
        "scene": "A lone figure seen from behind walks along an empty seawall at sunrise, warm light on the water.",
        "why_it_fits": "Morning light after a long effort reads as quiet pride at a glance.",
        "opening": "The figure walks slowly as small waves roll in.",
        "middle": "The wind moves their coat as the sun rises.",
        "ending": "They keep walking into the brightening light.",
        "search_themes": ["motivational quotes", "self love quotes", "keep going quotes"],
        "hashtag": "#newbeginnings",
        "emojis": ["🌅", "✨"],
    }
    data.update(overrides)
    return json.dumps(data)


# ---------------------------------------------------------------------------
# The contract fields: emotion, tone, search_themes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value, tone", [
    ("numb", "numb"), ("  Hopeful. ", "hopeful"), ("Sadness", "sad"), ("inspiring", "uplifting"),
    ("motivational", "empowering"), ("sad, lonely", "sad"), ("heartbreak", "heartbroken"), ("bittersweet", "bittersweet"),
    ("ecstatic", None), ("", None), (["sad"], None), (3, None), (None, None),
])
def test_the_tone_is_one_word_of_the_fixed_list_or_none(value, tone):
    assert fp.direction_tone(value) == tone
    assert tone is None or tone in fp.TONES


def test_the_emotion_is_a_short_lowercase_phrase():
    assert fp.direction_emotion("Guarded, numb after heartbreak.") == "guarded, numb after heartbreak"
    # Over six words keeps the leading clauses that fit, never half a clause.
    assert fp.direction_emotion("guarded, numb after heartbreak, afraid of being hurt again") == "guarded, numb after heartbreak"
    assert fp.direction_emotion("a very long single clause of more than six words") == "a very long single clause of"
    # A live director wrote eight words with no comma; the leading phrase is kept.
    assert fp.direction_emotion("quiet relief and gentle peace after years of pain") == "quiet relief"
    for bad in ("", "💔 broken", "#sad", ["sad"], None):
        assert fp.direction_emotion(bad) is None, bad


def test_search_themes_are_three_to_six_clean_phrases_or_none():
    themes = fp.direction_search_themes([
        "Heartbreak Quotes", "sad love quotes", "#sadquotes", "heartbreak quote", "sad 💔 quotes", "quotes",
        "a phrase of far too many words", 7, "self respect quotes", "emotional numbness", "moving on quotes",
        "healing quotes", "letting go quotes",
    ])
    assert themes == ["heartbreak quotes", "sad love quotes", "self respect quotes", "emotional numbness",
                      "moving on quotes", "healing quotes"]
    assert all(2 <= len(theme.split()) <= 4 and theme == theme.casefold() for theme in themes)
    assert fp.direction_search_themes(["heartbreak quotes", "#sad", "sad"]) is None  # fewer than three survive
    assert fp.direction_search_themes("heartbreak quotes") is None


def test_the_plan_carries_the_contract_fields_and_drops_invalid_ones():
    reply = director_reply(emotion="tired, but proud of every single small step forward", tone="ecstatic",
                           search_themes=["#motivation", "grind"])
    plan, answers = plan_with(reply, writer_reply(SUNRISE_WALK), quote=HOPEFUL, director=True)
    direction = plan["creative_direction"]
    assert list(direction) == ["quote_meaning", "scene", "why_it_fits", "opening", "middle", "ending",
                               "emotion", "tone", "search_themes", "hashtag", "emojis"]
    assert direction["emotion"] == "tired"  # the clause that fits in six words
    assert direction["tone"] is None and direction["search_themes"] is None
    assert len(answers.prompts) == 2 and plan["checks"]["passed"] is True


def test_long_director_text_is_cut_at_a_word():
    reply = director_reply(why_it_fits="word " * 100)
    plan, _ = plan_with(reply, writer_reply(SUNRISE_WALK), quote=PROUD, director=True)
    why = plan["creative_direction"]["why_it_fits"]
    assert len(why) <= 300 and why.endswith("word…")


# ---------------------------------------------------------------------------
# Stillness and motion
# ---------------------------------------------------------------------------

STILL_PHRASES = [
    "all movement and sound cease", "all motion stops", "comes to a complete stop", "comes to rest",
    "rests completely still", "completely still", "perfectly motionless", "motionless", "frozen in place",
    "a static photograph", "a still image", "stops moving", "near-static", "devoid of any movement",
    "everything goes still", "remaining entirely still", "nothing moves",
]


@pytest.mark.parametrize("phrase", STILL_PHRASES)
def test_every_stillness_phrase_is_found_and_taken_out(phrase):
    prompt = (
        "Wide shot, slow push-in on a 35mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
        f"A lone figure walks slowly along an empty seawall at blue dusk, waves rolling in below. In the ending, {phrase}. "
        "Cinematic natural light; the upper-middle stays calm for text added later. " + CLOSING
    )
    assert fp.stillness_phrases(prompt), phrase
    assert any("still frame" in issue for issue in fp.check_prompt(prompt, HEART, 1)[0])
    patched, added = fp.patch_prompt(prompt, part=1, audio="wind")
    assert not fp.stillness_phrases(patched), (phrase, patched)
    assert "a moving scene instead of a still frame" in added
    assert "waves rolling in below" in patched and fp.has_scene_motion(patched)
    assert "In the ending." not in patched and "In the ending," not in patched  # no bare beat is left behind
    assert fp.check_prompt(patched, HEART, 1)[0] == []


def test_a_held_pose_keeps_its_meaning_without_freezing_the_clip():
    for pose, rewritten in (("stands motionless", "stands quietly"), ("sits perfectly still", "sits quietly"),
                            ("standing still", "standing quietly"), ("keeps a still posture", "keeps a quiet posture")):
        sentence = f"A lone figure {pose} at the end of the pier as grey waves roll in."
        assert fp._drop_stillness(sentence)[0] == f"A lone figure {rewritten} at the end of the pier as grey waves roll in."


def test_a_clause_that_stops_the_scene_goes_and_the_rest_stays():
    assert fp._drop_stillness("The figure walks to the edge of the pier, then comes to a complete stop.")[0] == \
        "The figure walks to the edge of the pier."
    assert fp._drop_stillness("Waves roll in and all motion ceases as the light fades.")[0] == \
        "Waves roll in as the light fades."
    assert fp._drop_stillness("In the ending, all movement and sound cease as the bundle rests completely still.")[0] == ""


@pytest.mark.parametrize("text", [
    "The figure never stops moving along the shore.", "No still images, no frozen frames.",
    "The upper-middle of the frame stays completely still and uncluttered for the quote.",
    "A small boat rests on calm water as ripples spread.", "Two cups on the table, one still steaming.",
    "The camera holds steady while waves roll in.",
])
def test_calm_that_is_not_a_frozen_frame_is_left_alone(text):
    assert fp.stillness_phrases(text) == [], text


def test_a_camera_move_over_a_motionless_picture_gets_a_motion_line_that_fits_it():
    prompt = (
        "Wide shot, slow push-in on a 35mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
        "A lone figure in a dark coat, seen from behind, on an empty seawall at blue dusk. Cinematic natural light; "
        "the upper-middle stays calm for text added later. " + CLOSING
    )
    assert not fp.has_scene_motion(prompt)
    assert any("no visible motion" in issue for issue in fp.check_prompt(prompt, HEART, 1)[0])
    patched, added = fp.patch_prompt(prompt, part=1, audio="wind")
    assert "visible scene motion instead of a still life" in added
    sentences = fp._sentences(patched)
    # The motion line follows the sentence that names the figure, so nothing refers to it before.
    assert sentences[2].startswith("Visible motion: a steady breeze moves hair and clothing")
    assert fp.check_prompt(patched, HEART, 1)[0] == []
    # The camera's own movement is not motion in the scene.
    assert not fp.has_scene_motion("Slow drift to the left on a 35mm lens; the camera drifts toward an empty bench.")
    assert fp.has_scene_motion("Mist drifts across the tracks.")


# ---------------------------------------------------------------------------
# Symbols, figures of speech, crowds
# ---------------------------------------------------------------------------


def test_the_pocket_watch_prompt_is_flagged_and_its_stillness_removed():
    issues, _ = fp.check_prompt(POCKET_WATCH, HEART, 1)
    assert any("symbol viewers must decode (a watch, an object being wrapped or bound)" in issue for issue in issues)
    assert any("still frame" in issue for issue in issues)
    patched, _ = fp.patch_prompt(POCKET_WATCH, part=1, audio="wind")
    assert "rests completely still" not in patched and "all movement and sound cease" not in patched
    # Patching cannot make a symbol a real moment: that takes the repair call.
    assert any("symbol" in issue for issue in fp.check_prompt(patched, HEART, 1)[0])


def test_a_symbol_in_gemini_prompt_costs_the_repair_call_and_the_fixed_prompt_is_kept():
    plan, answers = plan_with(writer_reply(POCKET_WATCH), writer_reply(NIGHT_WALK))
    assert len(answers.prompts) == 2
    assert "single permitted revision" in answers.prompts[1] and "pocket watch" in answers.prompts[1]
    assert "symbol viewers must decode" in answers.prompts[1]
    assert plan["shots"][0]["prompt"].startswith("Wide shot, slow tracking move")
    assert plan["checks"]["passed"] is True


@pytest.mark.parametrize("text", [
    "They stop to watch the waves roll in.", "A clock tower stands in the distance as clouds drift.",
    "A figure walks through the heart of the old town.", "A scarf wrapped around her neck flutters.",
    "Two hands wrap around a warm cup as steam rises.", "A chain-link fence lines the empty road.",
    "The platform clock hangs above the far bench.", "A small paper boat drifts on the stream.",
    "An empty street with no masks, cages or clocks.",
])
def test_ordinary_things_are_not_symbols(text):
    assert fp.symbolic_props(text) == [], text


@pytest.mark.parametrize("text, name", [
    ("A gloved hand holds a vintage pocket watch.", "a watch"),
    ("A small silver locket swings from a chain.", "a locket"),
    ("A white mask lies on the table.", "a mask"),
    ("A bird sits in a cage by the window.", "a cage"),
    ("A red glass heart shatters on the floor.", "a heart-shaped object"),
    ("Sand slips through an hourglass.", "an hourglass"),
    ("Paper cranes hang over the bed.", "origami"),
    ("A ticking clock on the wall.", "a clock"),
    ("A marionette dangles from its strings.", "a puppet or doll"),
])
def test_symbols_are_named(text, name):
    assert name in fp.symbolic_props(text)


def test_figures_of_speech_and_crowds_are_issues():
    figurative = SUNRISE_WALK.replace("walks slowly along", "walks with a heavy heart along")
    assert any("figure of speech" in issue and "heavy heart" in issue for issue in fp.check_prompt(figurative, PROUD, 1)[0])
    crowded = SUNRISE_WALK.replace("an empty seawall", "a busy street of commuters")
    assert any("other people in the frame" in issue for issue in fp.check_prompt(crowded, PROUD, 1)[0])
    assert fp.crowd_word("an empty street with no other people or cars") == ""


# ---------------------------------------------------------------------------
# The subject is named before "they" or "their"
# ---------------------------------------------------------------------------

# The live failure: the opening beat was trimmed, leaving "their jacket" with no one in it.
PRONOUN_ONLY = (
    "Wide shot, slow push-in on a 35mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
    "Cinematic natural lighting at cold overcast dusk over an empty concrete pier. In the middle, the wind ripples "
    "their jacket as they pause near the end of the pier while grey waves roll below. The upper-middle of the frame "
    "stays calm, low-detail and uncluttered for text overlay. " + CLOSING
)


def test_a_beat_about_their_jacket_with_no_one_named_is_an_issue():
    assert fp.subject_gap(PRONOUN_ONLY) == "their jacket"
    issues, _ = fp.check_prompt(PRONOUN_ONLY, HEART, 1)
    assert any("'their jacket' comes before the prompt says who it is" in issue for issue in issues)
    named = PRONOUN_ONLY.replace("over an empty concrete pier.", "over an empty concrete pier, where a lone figure seen from behind walks.")
    assert fp.subject_gap(named) == ""
    # "They" about waves or leaves is not a person.
    assert fp.subject_gap("Waves roll in as they break on the sand; leaves tremble as they fall.") == ""


def test_an_unnamed_subject_is_repaired_and_named_locally_when_the_repair_fails_too():
    plan, answers = plan_with(writer_reply(PRONOUN_ONLY), writer_reply(NIGHT_WALK))
    assert len(answers.prompts) == 2 and "before the prompt says who it is" in answers.prompts[1]
    assert plan["shots"][0]["prompt"] == fp.patch_prompt(NIGHT_WALK, part=1, audio="wind and slow waves")[0]
    # The repair did not name anyone either: a lone figure is named rather than losing the scene to the library.
    plan, answers = plan_with(writer_reply(PRONOUN_ONLY), writer_reply(PRONOUN_ONLY))
    prompt = plan["shots"][0]["prompt"]
    assert plan["generation_source"] == "gemini" and plan["checks"]["passed"] is True
    assert "A lone figure, seen from behind, small in the lower third of the frame. In the middle, the wind ripples their jacket" in prompt
    assert any("a lone figure was named" in warning for warning in plan["checks"]["warnings"])


def test_trimming_keeps_the_sentence_that_names_the_subject():
    prompt = (
        "Wide shot, slow push-in on a 35mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
        "Cinematic natural light at cold dusk over an empty concrete pier above grey water. "
        "A lone figure in a dark coat, seen from behind, walks slowly toward the end of the pier. "
        + "The old boards are dark with spray and scattered with small pools that hold the pale sky. " * 6
        + "In the middle, the wind ripples their jacket as they keep walking. "
        "The upper-middle of the frame stays calm and uncluttered for text overlay. " + CLOSING
    )
    assert fp.word_count(prompt) > fp.MAX_PROMPT_WORDS
    trimmed = fp.trim_prompt(prompt, part=1)
    assert "A lone figure in a dark coat" in trimmed and fp.subject_gap(trimmed) == ""


# ---------------------------------------------------------------------------
# Light follows the tone
# ---------------------------------------------------------------------------


def test_a_hopeful_quote_at_night_costs_the_repair_and_the_sunrise_take_is_kept():
    plan, answers = plan_with(director_reply(), writer_reply(NIGHT_WALK), writer_reply(SUNRISE_WALK),
                              quote=HOPEFUL, director=True)
    assert len(answers.prompts) == 3  # director, writer, repair: never a fourth
    assert "the quote's tone is hopeful" in answers.prompts[1]
    assert "a hopeful quote needs sunrise or early golden hour" in answers.prompts[2] and "night" in answers.prompts[2]
    assert "at sunrise in warm golden light" in plan["shots"][0]["prompt"]
    assert plan["checks"]["passed"] is True
    assert not any("hopeful quote needs" in warning for warning in plan["checks"]["warnings"])


def test_a_hopeful_quote_left_at_night_after_the_repair_keeps_its_scene_with_a_warning():
    plan, answers = plan_with(director_reply(), writer_reply(NIGHT_WALK), writer_reply(NIGHT_WALK),
                              quote=HOPEFUL, director=True)
    assert len(answers.prompts) == 3
    # A well-made scene in the wrong light still fits better than the library's generic one.
    assert plan["generation_source"] == "gemini" and "at night under orange streetlights" in plan["shots"][0]["prompt"]
    assert plan["checks"]["passed"] is True
    assert any("a hopeful quote needs" in warning for warning in plan["checks"]["warnings"])


def test_light_mismatch_reads_gloom_that_ends_and_golden_dusk_as_hope():
    assert fp.light_mismatch("A figure walks home at night in the rain.", "hopeful") == "night, in the rain"
    assert fp.light_mismatch("After the storm, the clouds part and sunrise spreads over the field.", "healing") == ""
    assert fp.light_mismatch("A figure walks on the beach at a warm golden dusk.", "uplifting") == ""
    assert fp.light_mismatch("An empty road in bright sunshine under a clear blue sky.", "lonely") == "bright sunshine, clear blue sky"
    assert fp.light_mismatch("An empty road at night.", "nostalgic") == ""


def test_a_director_scene_in_the_wrong_light_is_corrected_for_the_writer():
    dusk = director_reply(scene="A lone figure seen from behind walks along an empty seawall at dusk, city lights glowing.")
    plan, answers = plan_with(dusk, writer_reply(SUNRISE_WALK), quote=HOPEFUL, director=True)
    writer_prompt = answers.prompts[1]
    assert "Correction to the direction: the scene is set in dusk, which does not fit a hopeful quote" in writer_prompt
    assert any("Creative direction set a hopeful quote in dusk" in warning for warning in plan["checks"]["warnings"])


def test_a_creators_own_light_is_kept():
    plan, answers = plan_with(director_reply(), writer_reply(NIGHT_WALK), quote=PROUD, director=True,
                              mood_hint="city at night")
    assert len(answers.prompts) == 2  # no repair for the light the creator asked for
    assert "the quote's tone is" not in answers.prompts[1]
    assert not any("hopeful quote needs" in warning for warning in plan["checks"]["warnings"])


# ---------------------------------------------------------------------------
# The director's own text
# ---------------------------------------------------------------------------


def test_stillness_and_crowds_in_the_direction_never_reach_the_writer():
    reply = director_reply(
        scene="A figure stands motionless on an empty seawall at sunrise as commuters rush past.",
        middle="The figure sits motionless, remaining entirely still.",
        ending="All movement ceases.",
    )
    plan, answers = plan_with(reply, writer_reply(SUNRISE_WALK), quote=PROUD, director=True)
    direction = plan["creative_direction"]
    assert direction["scene"] == "A figure stands quietly on an empty seawall at sunrise as commuters rush past."
    assert direction["middle"] == "The figure sits quietly."
    assert direction["ending"] == fp._KEEP_MOVING_BEAT
    writer_prompt = answers.prompts[1]
    assert "stands motionless" not in writer_prompt and "entirely still" not in writer_prompt
    assert "Correction to the direction: the scene has other people in it ('commuters')" in writer_prompt
    assert any("Creative direction asked for a still frame ('stands motionless')" in warning
               for warning in plan["checks"]["warnings"])


# ---------------------------------------------------------------------------
# Craft, Part 2+, length and the call budget
# ---------------------------------------------------------------------------


def test_a_missing_shot_size_camera_move_and_light_are_named_locally():
    bare = (
        "Vertical 9:16 portrait composition, one continuous 8-second shot. A lone figure seen from behind walks "
        "along an empty seawall as small waves roll in; the upper-middle stays clear for text added later. " + CLOSING
    )
    patched, added = fp.patch_prompt(bare, part=1, audio="wind", tone="hopeful")
    assert added == ["shot size", "camera move", "light and style sentence"]
    assert patched.startswith("Wide shot on a 35mm lens with a slow tracking move, vertical 9:16")
    assert "Cinematic natural light, sunrise or early golden hour" in patched
    assert fp.check_prompt(patched, PROUD, 1) == ([], [])
    extension, added = fp.patch_prompt(
        "Continuing the same scene: same location. The figure keeps walking as a gull passes overhead. " + CLOSING,
        part=2, audio="wind",
    )
    assert "same location. The same framing and the same slow camera move as the opening. The figure" in extension
    assert {"shot size", "camera move"} <= set(added)


def test_the_writers_own_cinematography_is_recognised_and_not_doubled():
    # A live prompt got "Wide shot with a slow push-in," in front of its own camera sentence.
    for opening in ("A wide eye-level shot slowly drifts forward on a 35mm lens",
                    "A wide-angle, slow continuous forward drift using a 35mm lens",
                    "An extreme wide shot with a slow continuous tracking backward move on a 35mm lens"):
        prompt = f"{opening}, vertical 9:16 portrait composition, one continuous 8-second shot. " + SUNRISE_WALK.split(". ", 1)[1]
        patched, added = fp.patch_prompt(prompt, part=1, audio="wind")
        assert added == [] and patched.startswith(opening), (opening, added)
    # Mist drifting is the scene moving, not a camera move.
    assert not fp._CAMERA_MOVE_RE.search("A figure waits as mist drifts over the tracks.")


def test_beat_labels_become_prose_and_a_reveal_becomes_a_first_frame_that_shows():
    # Live prompts wrote "Opening: ..." and "The opening reveals a lone figure ...".
    prompt = (
        "Wide shot, slow forward drift on a 35mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
        "The opening reveals a lone figure, seen from behind, sitting on a wide windowsill. Middle: a breeze shifts "
        "the fabric of the shirt as city lights flicker. Ending: the lights keep flickering below. Cool blue-teal "
        "tones; the upper-middle stays calm for text added later. " + CLOSING
    )
    patched, added = fp.patch_prompt(prompt, part=1, audio="wind")
    assert "The opening shows a lone figure" in patched and "reveal" not in patched
    assert "In the middle, a breeze shifts the fabric" in patched and "In the ending, the lights keep" in patched
    # The slow forward drift is the camera move; the window gets its no-reflection line.
    assert "Middle:" not in patched and added == ["no reflection of a face in the glass"]
    assert "No reflection of a face in the glass." in patched
    assert fp.check_prompt(patched, HEART, 1) == ([], [])


def test_a_part_two_that_repeats_part_one_is_repaired_or_rebuilt_with_a_development():
    opener = "Continuing the same seawall scene: same location, same camera height and lens, same light and palette. "
    copy = opener + NIGHT_WALK
    assert fp.repeats_previous(copy, NIGHT_WALK)
    developed = copy.replace(fp.NEGATIVE_PROMPT, "A single gull glides low over the water and the first lamp flickers on. " + fp.NEGATIVE_PROMPT)
    assert not fp.repeats_previous(developed, NIGHT_WALK)
    plan, answers = plan_with(writer_reply(NIGHT_WALK, copy), writer_reply(NIGHT_WALK, developed), parts=2)
    assert len(answers.prompts) == 2 and "repeats Part 1's action" in answers.prompts[1]
    assert "A single gull glides low" in plan["shots"][1]["prompt"] and plan["checks"]["passed"] is True
    # Copied twice: rebuilt from Part 1 with a development of its own, never left as a copy.
    plan, _ = plan_with(writer_reply(NIGHT_WALK, copy), writer_reply(NIGHT_WALK, copy), parts=2)
    assert plan["shots"][1]["prompt"].startswith("Continuing the same scene: same location, same framing")
    assert not fp.repeats_previous(plan["shots"][1]["prompt"], plan["shots"][0]["prompt"])
    assert plan["checks"]["passed"] is True


def test_length_alone_never_costs_a_gemini_call_and_no_op_trims_are_not_reported():
    beats = " ".join(f"In the {beat}, the wind moves their coat as they keep walking past harbour wall number {n}, "
                     f"its old stones dark with spray and salt." for n, beat in
                     enumerate(("opening", "middle", "ending", "opening", "middle", "ending")))
    long = NIGHT_WALK.replace("Cinematic natural light;", f"{beats} Cinematic natural light;")
    patched, _ = fp.patch_prompt(long, part=1, audio="wind and slow waves")
    assert fp.word_count(patched) > fp.MAX_PROMPT_WORDS
    plan, answers = plan_with(writer_reply(long))
    assert len(answers.prompts) == 1
    assert plan["generation_source"] == "gemini" and plan["checks"]["passed"] is True
    # The ceiling is met by trimming, protected beats losing their last clause if need be.
    assert fp.word_count(plan["shots"][0]["prompt"]) <= fp.MAX_PROMPT_WORDS
    assert not any(re.search(r"trimmed from (\d+) to \1 words", warning) for warning in plan["checks"]["warnings"])


def test_the_planner_never_makes_a_fourth_call():
    bad = writer_reply(POCKET_WATCH)
    plan, answers = plan_with(director_reply(), bad, bad, quote=PROUD, director=True)
    assert len(answers.prompts) == 3
    assert plan["generation_source"] == "fallback" and plan["checks"]["passed"] is True
    assert plan["provider"] == {}


def test_without_a_direction_the_writer_reads_the_quote_itself():
    prompt = fp._build_plan_prompt(HEART, language="english", parts=1, mood_hint="", feeling="love unreturned")
    assert "love unreturned" not in prompt and "Feeling read locally" not in prompt
    assert "protecting yourself by feeling nothing is not unrequited love" in prompt
    assert "no crowds" in prompt and "avoid rain and wet streets" in prompt
    assert "a shot size (wide, medium or close), one slow camera move" in prompt


# ---------------------------------------------------------------------------
# The reading of the quote outlives its scene; the library reads the tone
# ---------------------------------------------------------------------------

HEALED = "My heart finally healed, and I didn't even notice when."
UNDERSTANDING_KEYS = ("quote_meaning", "emotion", "tone", "search_themes")


def offline(quote: str, **kwargs) -> dict:
    with patch.object(gemini_client, "is_available", return_value=False):
        return fp.plan_flow_shots(quote, **kwargs)


def test_the_understanding_is_kept_when_the_library_writes_the_shots():
    bad = writer_reply(POCKET_WATCH)
    plan, answers = plan_with(director_reply(), bad, bad, quote=HOPEFUL, director=True)
    assert len(answers.prompts) == 3 and plan["generation_source"] == "fallback"
    assert "creative_direction" not in plan
    assert plan["quote_understanding"] == {
        "quote_meaning": "Encouragement for someone exhausted by effort nobody sees.",
        "emotion": "tired but quietly proud", "tone": "hopeful",
        "search_themes": ["motivational quotes", "self love quotes", "keep going quotes"],
        "hashtag": "#newbeginnings", "emojis": ["🌅", "✨"],
    }
    # The director's hopeful tone picked the library's dawn scene, not the lexicon's quiet lake.
    assert plan["shots"] == fp.fallback_shots(HOPEFUL, 1, "healing")
    assert plan["mood"]["feeling"] == "tired but quietly proud" and plan["mood"]["keywords"][0] == "hopeful"
    assert plan["checks"]["passed"] is True


def test_a_director_reply_without_a_scene_still_gives_its_reading():
    partial = json.loads(director_reply(search_themes=["#motivation", "grind"]))
    for key in ("scene", "why_it_fits", "opening", "middle", "ending", "candidates"):
        partial.pop(key)
    plan, answers = plan_with(json.dumps(partial), writer_reply(SUNRISE_WALK), quote=HOPEFUL, director=True)
    assert plan["quote_understanding"] == {
        "quote_meaning": "Encouragement for someone exhausted by effort nobody sees.",
        "emotion": "tired but quietly proud", "tone": "hopeful", "search_themes": None,
        "hashtag": "#newbeginnings", "emojis": ["🌅", "✨"],
    }
    assert "creative_direction" not in plan
    writer_prompt = answers.prompts[1]
    assert "Encouragement for someone exhausted" in writer_prompt and "the quote's tone is hopeful" in writer_prompt
    assert any(warning.startswith("Creative direction gave no usable scene (missing scene, why_it_fits")
               for warning in plan["checks"]["warnings"])


def test_no_understanding_without_a_director_that_answered():
    assert "quote_understanding" not in offline(PROUD)
    refused = {"status": "gemini_budget_exhausted", "failure_category": "request_budget_exhausted"}
    answers = iter([("", refused), (writer_reply(SUNRISE_WALK), TRACE)])
    with patch.multiple(gemini_client, is_available=lambda: True,
                        generate_with_diagnostics=lambda prompt, system="", **kwargs: next(answers)):
        plan = fp.plan_flow_shots(PROUD, parts=1, creative_direction=True)
    assert "quote_understanding" not in plan and "creative_direction" not in plan
    # Without the director, only the writer's mood (never the reading it lacks).
    assert plan["generation_source"] == "gemini"


def test_without_gemini_the_heart_quote_is_not_read_as_unrequited_love():
    plan = offline(HEART, parts=2)
    heartbreak = fp._scene_for("love unreturned")
    assert plan["mood"]["feeling"] != "love unreturned"
    assert plan["mood"]["visual_metaphor"] != heartbreak.metaphor
    assert not any(subject in shot["prompt"] for shot in plan["shots"] for subject in heartbreak.subjects)
    # "To not get your heart broken ... pretend you don't have one" is guarded numbness: the lone night bench.
    assert plan["mood"]["feeling"] == "loneliness"
    assert plan["checks"]["passed"] is True


def test_without_gemini_a_healed_heart_gets_the_healing_scene():
    plan = offline(HEALED)
    assert plan["mood"]["feeling"] == "healing"
    assert plan["mood"]["visual_metaphor"] == fp._scene_for("healing").metaphor
    assert any(context in plan["shots"][0]["prompt"] for context in fp._scene_for("healing").contexts)


def test_the_lexicon_stands_when_the_tone_accepts_it_or_the_creator_chose():
    # The tone reads "empowering" and accepts the lexicon's "being misunderstood".
    assert fp.library_feeling("Stop explaining yourself to people who already decided to misunderstand you")[0] == \
        "being misunderstood"
    assert fp.library_feeling("I still check my phone hoping it is you")[0] == "missing someone"  # no tone read
    assert fp.library_feeling(HEART, "unrequited love")[0] == "love unreturned"  # the creator's hint decides
    assert fp.library_feeling(PROUD, tone="empowering")[0] == "strength"
    assert fp.library_feeling(PROUD, tone="hopeful")[0] == "healing"


def test_a_local_tone_that_cannot_be_read_leaves_the_lexicon():
    with patch("win_engine.generation.ai_shorts_seo.local_tone", side_effect=RuntimeError("boom")):
        assert fp.library_feeling(HEART)[0] == "love unreturned"


# ---------------------------------------------------------------------------
# Round 2: safety, variety, tone, themes, hashtag and emojis, craft, overlay
# ---------------------------------------------------------------------------

DISCIPLINE = "Discipline is doing it even when you don't feel like it."
ROOFTOP = (
    "Wide shot, slow push-in on a 50mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
    "A lone figure in a grey hoodie, seen from behind, sits quietly near the edge of a high concrete rooftop at "
    "night as city lights flicker far below and the wind moves their hood. Cool blue-teal tones; the upper-middle "
    "stays dark and calm. " + CLOSING
)
SAD_DIRECTOR = json.loads(director_reply(
    quote_meaning="Someone hurt before now acts as if nothing touches them.", emotion="guarded, numb", tone="numb",
    scene="A lone figure sits near the edge of a high rooftop at night as city lights glitter below.",
    candidates=["A figure sits on a rooftop ledge at night.", "A figure walks along an empty seawall at blue dusk.",
                "A lone bus shelter at night as headlights pass."],
))


def test_a_sad_quote_is_kept_off_heights_in_the_prompt():
    plan, answers = plan_with(writer_reply(ROOFTOP), writer_reply(NIGHT_WALK))  # HEART reads numb by its own words
    assert len(answers.prompts) == 2
    assert "keep the subject on level, safe ground" in answers.prompts[0]
    assert "a sad quote is set at a height ('rooftop')" in answers.prompts[1]
    assert "rooftop" not in plan["shots"][0]["prompt"] and plan["checks"]["passed"] is True
    # A hopeful quote may stand on a balcony at sunrise.
    shot = {"part": 1, "seconds": 8, "title": "t", "flow_mode": "text_to_video", "continuity": None,
            "prompt": SUNRISE_WALK.replace("seawall", "balcony")}
    assert fp.check_plan({"parts": 1, "shots": [shot], "mood": {"pace": "slow"}}, HOPEFUL, tone="hopeful")["passed"] is True


def test_a_director_scene_at_a_height_for_a_sad_quote_is_dropped():
    plan, answers = plan_with(json.dumps(SAD_DIRECTOR), writer_reply(NIGHT_WALK), director=True)
    writer_prompt = answers.prompts[1]
    # The reading stays and the next safe candidate becomes the scene.
    assert plan["creative_direction"]["scene"] == "A figure walks along an empty seawall at blue dusk."
    assert plan["quote_understanding"]["tone"] == "numb"
    assert "high rooftop" not in writer_prompt and "rooftop ledge" not in writer_prompt
    assert "empty seawall at blue dusk" in writer_prompt
    assert any("Creative direction set a numb quote at a height (rooftop)" in warning and "next candidate" in warning
               for warning in plan["checks"]["warnings"])
    assert fp.unsafe_height("a figure on a bench in the park") == ""
    assert fp.unsafe_height("standing by the metal railing of a high-rise balcony") == "railing"


def test_recent_scenes_are_avoided_by_the_director_and_a_repeat_is_dropped():
    recent = ["A lone figure walks up a winding dirt path on a grassy hillside at golden hour."]
    repeat = director_reply(
        scene="A lone figure walks up a long winding path on a hillside at sunrise.",
        candidates=["A figure walks up a hill path at sunrise.", "A ferry crosses a calm bay at dawn.",
                    "A kite rises over a field at golden hour."],
    )
    plan, answers = plan_with(repeat, writer_reply(SUNRISE_WALK), writer_reply(SUNRISE_WALK), quote=HOPEFUL,
                              director=True, avoid_scenes=recent)
    director_prompt, writer_prompt = answers.prompts[:2]
    assert "Already used on this channel" in director_prompt
    assert "winding dirt path on a grassy hillside" in director_prompt
    assert "Scenes already used on this channel" in writer_prompt
    assert any(warning.startswith("Creative direction repeated a recent scene") for warning in plan["checks"]["warnings"])
    assert "ferry crosses a calm bay" in writer_prompt and "A figure walks up a hill path" not in writer_prompt
    assert fp.scene_repeats("A woman walks up the hill path at dawn.", recent)
    assert not fp.scene_repeats("A ferry crosses a calm bay at dawn.", recent)
    assert not fp.scene_repeats("A lone figure walks along the beach.", recent)  # figure and walk alone are no repeat
    # A repeat that reaches the prompt is named, never paid for with a call.
    plan, answers = plan_with(writer_reply(SUNRISE_WALK),
                              avoid_scenes=["A lone figure walks along an empty seawall at dusk."])
    assert len(answers.prompts) == 1
    assert any(warning.startswith("Part 1 repeats a recent scene") for warning in plan["checks"]["warnings"])


def test_the_director_is_asked_for_variety_safety_and_the_quotes_own_topic():
    prompt = fp._director_prompt(HEART, "")
    for text in (
        "not always a figure in a dark coat", "the lens (24mm to 85mm)", "an empty place that carries the feeling",
        "do not add a loss, a breakup, an absence or any event the quote doesn't state",
        "no rooftops, ledges, railings, balconies, bridges, cliff edges, overlooks",
        "most specific first", "missing someone quotes", "never invented long phrases",
        "hashtag", "#tamilquotes", "emojis", "Discipline and effort are empowering",
    ):
        assert text in prompt, text
    assert "Already used on this channel" not in prompt  # nothing recent was given


def test_the_quotes_own_words_settle_a_tone_the_director_confused():
    plan, answers = plan_with(director_reply(tone="hopeful"), writer_reply(SUNRISE_WALK), quote=DISCIPLINE, director=True)
    assert plan["quote_understanding"]["tone"] == plan["creative_direction"]["tone"] == "empowering"
    assert "the quote's tone is empowering" in answers.prompts[1]
    assert any("the quote's own words say empowering" in warning for warning in plan["checks"]["warnings"])
    assert fp.reconciled_tone(HEALED, "sad") == "healing"
    assert fp.reconciled_tone(HOPEFUL, "uplifting") == "uplifting"  # hopeful is not one of the precise few
    assert fp.reconciled_tone(DISCIPLINE, "empowering") == "empowering"


def test_search_themes_may_lead_with_a_longer_topic_phrase():
    themes = fp.direction_search_themes(["everything happens for a reason quotes", "hope quotes", "life quotes"])
    assert themes == ["everything happens for a reason quotes", "hope quotes", "life quotes"]


@pytest.mark.parametrize("value, tag", [
    ("#selfrespect", "#selfrespect"), ("SelfRespect", "#selfrespect"), ("#movingon.", "#movingon"),
    (["#love", "#home"], "#love"), ("#tamilquotes", "#tamilquotes"), ("#self respect", None), ("#ok", None),
    ("#self_respect", None), ("#" + "a" * 25, None), (None, None), (5, None),
])
def test_the_hashtag_is_one_lowercase_tag(value, tag):
    assert fp.direction_hashtag(value) == tag


def test_the_emojis_are_one_to_three_emoji():
    assert fp.direction_emojis(["🖤", "💔"]) == ["🖤", "💔"]
    assert fp.direction_emojis("💔🥀") == ["💔", "🥀"]
    assert fp.direction_emojis(["❤️", "🏡", "✨", "🌅"]) == ["❤️", "🏡", "✨"]
    assert fp.direction_emojis(["🖤", "🖤"]) == ["🖤"]
    for bad in (["sad"], ["#love"], "love ❤️", [], "", None, [1]):
        assert fp.direction_emojis(bad) is None, bad


def test_hashtag_and_emojis_reach_both_contract_blocks():
    plan, _ = plan_with(director_reply(), writer_reply(SUNRISE_WALK), quote=HOPEFUL, director=True)
    for block in (plan["creative_direction"], plan["quote_understanding"]):
        assert block["hashtag"] == "#newbeginnings" and block["emojis"] == ["🌅", "✨"]
    assert list(plan["quote_understanding"]) == ["quote_meaning", "emotion", "tone", "search_themes", "hashtag", "emojis"]


def test_a_static_camera_beside_a_named_move_loses_static():
    prompt = SUNRISE_WALK.replace("Wide shot, slow tracking move", "Wide static shot with a slow tracking move")
    patched, added = fp.patch_prompt(prompt, part=1, audio="wind")
    assert patched.startswith("Wide shot with a slow tracking move")
    assert "one camera move instead of a static camera" in added
    still_camera = SUNRISE_WALK.replace("Wide shot, slow tracking move on a 35mm lens", "Wide static shot on a 35mm lens")
    assert "static" in fp.patch_prompt(still_camera, part=1, audio="wind")[0]  # no move named: static stays


def test_the_light_holds_for_the_whole_clip():
    for shift in ("the warm sunset light gently yielding to deep blue tones",
                  "the warm light fades into cool blue dusk",
                  "the sky slowly shifts from pale amber to bright morning gold",
                  "the warm sun fully clears the horizon"):
        prompt = SUNRISE_WALK.replace("keep walking toward the horizon.", f"keep walking toward the horizon as {shift}.")
        patched, added = fp.patch_prompt(prompt, part=1, audio="wind")
        assert shift not in patched and "one light for the whole clip" in added, shift
        assert "keep walking toward the horizon" in patched and fp.check_prompt(patched, HOPEFUL, 1)[0] == []
    assert not fp._LIGHT_SHIFT_RE.search("A car moves from left to right as mist drifts into the valley.")


def test_a_part_two_that_only_changes_the_light_repeats_part_one():
    opener = "Continuing the same seawall scene: same location, same camera height and lens, same light and palette. "
    light_only = opener + SUNRISE_WALK.replace(
        fp.NEGATIVE_PROMPT, "The warm golden light now glows brighter across the whole sky. " + fp.NEGATIVE_PROMPT,
    )
    assert fp.repeats_previous(light_only, SUNRISE_WALK)
    moving = opener + SUNRISE_WALK.replace(
        fp.NEGATIVE_PROMPT, "A flock of gulls lifts off the water and glides past. " + fp.NEGATIVE_PROMPT,
    )
    assert not fp.repeats_previous(moving, SUNRISE_WALK)


def test_fused_beat_words_become_prose():
    text = ("The opening small silhouette stands quietly by the glass while the middle soft orange streetlights "
            "flicker below, and the ending shows the figure turning slightly.")
    plain = fp._plain_prompt_text(text)
    assert plain.startswith("In the opening, the small silhouette stands quietly")
    assert "while in the middle, the soft orange streetlights flicker below" in plain
    assert "the ending shows the figure" in plain


def test_a_prompt_that_forgot_the_text_area_gets_a_calm_upper_middle():
    # A live discipline prompt had no upper-middle sentence at all.
    prompt = SUNRISE_WALK.replace(
        " Cinematic natural light; the upper-middle stays calm, uncluttered and in soft focus for text added later.",
        " Cinematic natural light.",
    )
    assert "upper-middle" not in prompt
    patched, added = fp.patch_prompt(prompt, part=1, audio="wind")
    assert "The upper-middle of the frame stays calm, darker and in soft focus." in patched
    assert "a calm upper-middle" in added and fp.check_prompt(patched, HOPEFUL, 1) == ([], [])


def test_meta_text_about_the_overlay_is_taken_out():
    plain = fp._plain_prompt_text("The upper-middle stays calm and in soft focus so text can be laid over it later. "
                                  "The upper third stays clear for text overlay.")
    assert plain == "The upper-middle stays calm and in soft focus. The upper third stays clear."


def test_overlay_lines_never_strand_a_word():
    assert fp.split_overlay_lines(DISCIPLINE, 2) == [["Discipline is doing it"], ["even when you don't feel like it."]]
    missing = "You can miss someone and still know you're better without them."
    assert fp.split_overlay_lines(missing, 2) == [["You can miss someone"], ["and still know you're better without them."]]
    # Model splits that strand "even", split a clause across parts, or leave a two-word scrap give way.
    stranded = {"overlay_lines": [["Discipline is doing it even"], ["when you don't feel like it."]]}
    assert fp._overlay_from_reply(stranded, DISCIPLINE, 2) is None
    clause = {"overlay_lines": [["You can miss someone", "and still know"], ["you're better", "without them."]]}
    assert fp._overlay_from_reply(clause, missing, 2) is None
    silence = "Silence is the best answer to someone who doesn't value your words."
    scrap = {"overlay_lines": [["Silence is the best answer", "to someone"], ["who doesn't value your words."]]}
    assert fp._overlay_from_reply(scrap, silence, 2) is None
    heart = {"overlay_lines": [["The best way to not get your heart broken", "is to pretend"], ["that you don't", "have one."]]}
    assert fp._overlay_from_reply(heart, HEART, 2) is None  # a live split ended a line on "don't"
    good = {"overlay_lines": [["You can miss someone"], ["and still know you're better without them."]]}
    assert fp._overlay_from_reply(good, missing, 2) == [["You can miss someone"], ["and still know you're better without them."]]
    # A live split read "Be proud of how / hard you are trying": a question word leads its clause.
    proud = fp.split_overlay_lines("Be proud of how hard you are trying.", 2)
    assert all(not group[-1].split()[-1].casefold().strip(".,;:!?") in {"how", "of"} for group in proud)
    assert " ".join(line for group in proud for line in group) == "Be proud of how hard you are trying."


# ---------------------------------------------------------------------------
# Round 3: keep the quote through variety, rotation, output bugs, Veo feasibility, tone and themes
# ---------------------------------------------------------------------------


def test_a_repeat_is_a_shared_setting_and_the_same_action():
    porch = ["A woman sits on a wooden porch at dusk as wind chimes sway."]
    assert not fp.scene_repeats("A runner jogs along a wooden porch at dawn.", porch)  # same place, other action
    assert fp.scene_repeats("A man sits on the porch steps at night as leaves blow past.", porch)
    walker = ["A person in a coat walking slowly along an empty seawall at dusk."]
    assert not fp.scene_repeats("A person walking slowly along a forest trail at dawn.", walker)  # shared words only


def test_a_repeated_director_scene_keeps_the_reading_and_uses_the_next_candidate():
    stars = "Stars can't shine without darkness."
    recent = ["A cyclist rides along a coastal road at dusk."]
    reply = director_reply(
        quote_meaning="Hard times are what let your light show.", tone="hopeful",
        scene="A cyclist rides along a coastal road at night under the stars.",
        candidates=["A cyclist rides along a coastal road at dusk.",
                    "A figure lies in a dark field watching stars wheel overhead.",
                    "A lighthouse beam sweeps a dark sea."],
    )
    starry = SUNRISE_WALK.replace("walks slowly along an empty seawall at sunrise in warm golden light",
                                  "lies in a dark field under a starry night sky as the stars wheel overhead")
    plan, answers = plan_with(reply, writer_reply(starry), quote=stars, director=True, avoid_scenes=recent)
    assert plan["creative_direction"]["scene"] == "A figure lies in a dark field watching stars wheel overhead."
    assert plan["creative_direction"]["quote_meaning"] == "Hard times are what let your light show."
    assert "stars wheel overhead" in answers.prompts[1]
    # Night under the stars is the quote's own imagery, not gloom against a hopeful tone.
    assert fp.light_mismatch("A figure lies in a dark field at night under the stars.", "hopeful", stars) == ""
    assert fp.light_mismatch("A figure lies in a dark field at night.", "hopeful", "Keep going.") == "night"


def test_composition_and_light_wording_rotate():
    compositions = {fp._composition(f"quote number {n}", []) for n in range(16)}
    assert len(compositions) >= 4 and any("no person at all" in item for item in compositions)
    assert any("85mm" in item for item in compositions) and any("24mm" in item for item in compositions)
    lights = {fp.tone_light("empowering", f"quote number {n}") for n in range(16)}
    assert len(lights) == 3 and fp._TONE_LIGHT["empowering"] in lights
    assert "for this video prefer" in fp._build_plan_prompt(HEART, language="english", parts=1, mood_hint="", feeling="x")
    assert "for this video prefer" in fp._director_prompt(HEART, "")


def test_overlay_parts_are_balanced():
    quote = "The people who hurt you the most are the ones who said they never would."
    groups = fp.split_overlay_lines(quote, 3)
    assert groups == [["The people who hurt you the most"], ["are the ones"], ["who said they never would."]]
    counts = [len(" ".join(group).split()) for group in groups]
    assert min(counts) >= 0.6 * sum(counts) / 3
    lopsided = {"overlay_lines": [["The people"], ["who hurt you the most are the ones"], ["who said they never would."]]}
    assert fp._overlay_from_reply(lopsided, quote, 3) is None


def test_indoor_motion_is_steam_or_curtains_and_never_a_light_change():
    kitchen = (
        "Medium shot, slow push-in on a 50mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
        "A woman seen side-on sits at a small kitchen table with a mug of tea. Warm lamp light; the upper-middle stays "
        "calm. " + CLOSING
    )
    patched, added = fp.patch_prompt(kitchen, part=1, audio="a quiet kitchen")
    assert "Visible motion: steam rises and curls slowly from the cup throughout the shot." in patched
    assert "hair and clothing" not in patched and "light shifts" not in patched
    for _, line in fp._MOTION_LINES:
        assert "light shifts" not in line and "shifting light" not in line


def test_a_named_glide_or_pan_is_the_camera_move():
    for move in ("a sideways glide", "one slow arc around the bench", "the camera pans left", "a gentle dolly forward"):
        assert fp._CAMERA_MOVE_RE.search(f"Wide shot on a 35mm lens with {move}."), move
    prompt = SUNRISE_WALK.replace("Wide shot, slow tracking move on a 35mm lens", "Wide shot on a 35mm lens, a sideways glide")
    patched, added = fp.patch_prompt(prompt, part=1, audio="wind")
    assert "camera move" not in added and "push-in" not in patched


def test_a_layout_sentence_is_not_doubled():
    prompt = SUNRISE_WALK.replace(
        "Cinematic natural light; the upper-middle stays calm, uncluttered and in soft focus for text added later.",
        "Cinematic natural light and a calm, darker upper frame with soft focus.",
    )
    patched, _ = fp.patch_prompt(prompt, part=1, audio="wind")
    assert "The upper-middle of the frame stays calm" not in patched
    doubled = SUNRISE_WALK.replace(fp.NEGATIVE_PROMPT, "The sea stays calm. The sea stays calm. " + fp.NEGATIVE_PROMPT)
    assert fp.patch_prompt(doubled, part=1, audio="wind")[0].count("The sea stays calm.") == 1


def test_veo_feasibility_head_turns_hands_public_places_danger_and_location():
    turned = SUNRISE_WALK.replace("keep walking toward the horizon.",
                                  "keep walking toward the horizon, then slowly turn their head.")
    assert any("turns the head" in issue for issue in fp.check_prompt(turned, HOPEFUL, 1)[0])
    patched, added = fp.patch_prompt(turned, part=1, audio="wind")
    assert "turn their head" not in patched and "no head turning toward the camera" in added
    hands = fp.patch_prompt(SUNRISE_WALK.replace(
        "A lone figure in a dark coat, seen from behind and small in the lower third, walks",
        "Two hands, seen from behind, cradle a cup while a lone figure walks",
    ), part=1, audio="wind")[0]
    assert "Two hands, seen side-on" in hands
    diner = SUNRISE_WALK.replace("along an empty seawall", "past the window of a late-night diner")
    patched, added = fp.patch_prompt(diner, part=1, audio="wind")
    assert "The place is empty, with no other people anywhere in the frame." in patched and "an empty public place" in added
    danger = SUNRISE_WALK.replace("walks slowly along an empty seawall", "stands at the open door of a moving train")
    assert any("in danger" in issue for issue in fp.check_prompt(danger, HOPEFUL, 1)[0])
    part1 = "A woman stands at the door of a train carriage as fields rush past the glass. " + CLOSING
    part2 = ("Continuing the same scene: same location. A woman waits on an empty station platform as the wind moves "
             "her coat. " + CLOSING)
    assert fp.changes_place(part2, part1)
    assert any("moves to a different place" in issue for issue in fp._extension_issues(part2, part1, 2))
    assert not fp.changes_place("Continuing the same scene. The same woman stands at the train carriage door. " + CLOSING, part1)


def test_tone_and_themes_follow_the_quote():
    energy = "Be the energy you want to attract."
    assert fp.reconciled_tone(energy, "uplifting") == "uplifting"  # empowering wins only for discipline and effort
    assert fp.reconciled_tone("Discipline is doing it even when you don't feel like it.", "hopeful") == "empowering"
    prompt = fp._director_prompt("Home is not a place, it's a person.", "")
    assert "Home is not a place, it's a person" in prompt and "is love and belonging" in prompt
    assert "positive energy, gratitude and self-love are uplifting" in prompt
    for theme in ("mother quotes", "friendship quotes", "positive energy quotes", "hindi shayari"):
        assert theme in prompt, theme
    assert fp.with_language_theme(["sad quotes", "life quotes", "love quotes"], "dil se", "hinglish") == \
        ["sad quotes", "hindi shayari", "life quotes", "love quotes"]
    assert fp.with_language_theme(["sad quotes"], "कभी कभी चुप रहना", "english") == ["sad quotes", "hindi shayari"]
    assert fp.with_language_theme(["sad quotes", "deep quotes", "life quotes"], "Kashtam vandha", "tanglish")[1] == "tamil quotes"
    assert fp.with_language_theme(["sad quotes"], "Keep going.", "english") == ["sad quotes"]


# ---------------------------------------------------------------------------
# Round 4: the quote's own subject, a faithful writer, one framing, repeats that stay different
# ---------------------------------------------------------------------------

MOTHER = "My mother's hands carried my whole world."
BENCH = SUNRISE_WALK.replace(
    "A lone figure in a dark coat, seen from behind and small in the lower third, walks slowly along an empty seawall",
    "An empty wooden bench sits on a high grassy ridge as wind bends the grass, small in the lower third,",
)
MOTHER_WALK = SUNRISE_WALK.replace(
    "A lone figure in a dark coat, seen from behind and small in the lower third, walks slowly along an empty seawall",
    "A mother and her small child, seen from behind and small in the lower third, walk hand in hand along an empty seawall",
)


def test_the_quotes_relationship_and_imagery_must_be_shown():
    gaps = fp.subject_gaps(MOTHER, SUNRISE_WALK)
    assert gaps and "the quote names a mother" in gaps[0] and "mother and child" in gaps[0]
    assert fp.subject_gaps(MOTHER, MOTHER_WALK) == []
    assert fp.subject_gaps("Ammavin anbu pol ulagil vera edhuvum illai", SUNRISE_WALK)  # amma: a mother
    assert fp.subject_gaps("Stars can't shine without darkness.", SUNRISE_WALK)
    assert fp.imagery_light("Stars can't shine without darkness.") == "night under a clear starry sky"
    assert "storm clouds" in fp.imagery_light("After every storm the sky clears.")
    assert fp.imagery_light("Be proud of how hard you are trying.") == ""
    prompt = fp._build_plan_prompt("Stars can't shine without darkness.", language="english", parts=1, mood_hint="",
                                   feeling="x", tone="hopeful", imagery=fp.imagery_light("Stars can't shine without darkness."))
    assert "light the scene with night under a clear starry sky, whatever the tone's usual light" in prompt
    assert "the quote's tone is hopeful" not in prompt
    director = fp._director_prompt(MOTHER, "")
    assert "the scene should show that relationship literally" in director and "stars mean night" in director


def test_a_writer_that_leaves_out_the_mother_costs_the_repair():
    plan, answers = plan_with(writer_reply(SUNRISE_WALK), writer_reply(MOTHER_WALK), quote=MOTHER)
    assert len(answers.prompts) == 2 and "the quote names a mother" in answers.prompts[1]
    assert "mother and her small child" in plan["shots"][0]["prompt"]


def test_a_director_scene_without_the_mother_swaps_to_a_candidate_that_shows_her():
    reply = director_reply(
        quote_meaning="A mother's care held the whole family together.", tone="romantic",
        scene="A young woman walks alone along a beach at golden hour.",
        candidates=["A young woman walks alone along a beach at golden hour.",
                    "A mother and her small child walk hand in hand along an empty seawall at golden hour.",
                    "A kite flies over a field."],
    )
    plan, answers = plan_with(reply, writer_reply(MOTHER_WALK), quote=MOTHER, director=True)
    assert plan["creative_direction"]["scene"] == "A mother and her small child walk hand in hand along an empty seawall at golden hour."
    assert any("left out a mother" in warning for warning in plan["checks"]["warnings"])


def test_an_unfaithful_writer_is_repaired_and_the_page_shows_what_is_filmed():
    sailboat = director_reply(scene="A small sailboat glides across a calm lake at golden hour, its sail rippling.",
                              opening="The sailboat glides.", middle="The sail ripples.", ending="Ripples spread.")
    assert fp.unfaithful_to("A small sailboat glides across a calm lake at golden hour.", BENCH) == ["lake", "sailboat"]
    plan, answers = plan_with(sailboat, writer_reply(BENCH), writer_reply(BENCH), quote=HOPEFUL, director=True)
    assert len(answers.prompts) == 3 and "does not film the chosen scene" in answers.prompts[2]
    # Still a bench after the repair: the direction now names the bench, never a sailboat the prompt does not film.
    assert "bench" in plan["creative_direction"]["scene"] and "sailboat" not in plan["creative_direction"]["scene"]
    assert any("films a different scene" in warning for warning in plan["checks"]["warnings"])
    assert plan["generation_source"] == "gemini" and plan["checks"]["passed"] is True


def test_one_framing_per_description():
    both = SUNRISE_WALK.replace("seen from behind and small", "seen entirely from behind as a side-on silhouette, small")
    behind, added = fp.patch_prompt(both, part=1, audio="wind")
    assert "seen entirely from behind" in behind and "side-on silhouette" not in behind and "one framing" in added
    side, _ = fp.patch_prompt(both, part=1, audio="wind", framing="side")
    assert "side-on silhouette" in side and "from behind" not in side


def test_a_repeat_never_swaps_to_the_same_setting_and_keeps_its_own_scene_when_all_repeat():
    recent = ["A woman walks along a quiet beach at golden hour."]
    reply = director_reply(
        scene="A man walks along a wide beach at sunset as waves roll in.",
        candidates=["A girl walks along a sandy beach at dawn.", "A ferry crosses a calm bay at dawn.",
                    "A kite flies over a field."],
    )
    plan, _ = plan_with(reply, writer_reply(SUNRISE_WALK), writer_reply(SUNRISE_WALK), quote=HOPEFUL,
                        director=True, avoid_scenes=recent)
    assert "beach" not in plan["creative_direction"]["scene"] or "ferry" in plan["creative_direction"]["scene"]
    all_repeat = director_reply(
        scene="A man walks along a wide beach at sunset as waves roll in.",
        candidates=["A girl walks along a sandy beach at dawn.", "A boy walks along the beach at noon.",
                    "A woman walks on the beach at dusk."],
    )
    plan, answers = plan_with(all_repeat, writer_reply(SUNRISE_WALK), writer_reply(SUNRISE_WALK), quote=HOPEFUL,
                              director=True, avoid_scenes=recent)
    assert "change the lens, the framing" in answers.prompts[1]
    assert any("so did every candidate" in warning for warning in plan["checks"]["warnings"])


# ---------------------------------------------------------------------------
# External review: a repair that fails to bring back the quote's subject must not pass
# ---------------------------------------------------------------------------

MOTHER_DIRECTOR = director_reply(
    quote_meaning="A mother's care held up the whole of a child's life.", emotion="grateful, deep love", tone="romantic",
    scene="A mother and her small child walk hand in hand along an empty seawall at golden hour.",
    opening="The mother and child walk slowly as small waves roll in.", middle="The wind moves their coats.",
    ending="They keep walking toward the horizon.",
    candidates=["A mother and her small child walk hand in hand along an empty seawall at golden hour.",
                "An older woman's and a child's hands knead dough side-on at a kitchen table.",
                "A mother and child watch a kite rise over a field."],
)


def test_the_reviewers_sequence_fails_when_the_repair_still_drops_the_mother():
    # Director: the mother is in the scene. Writer and repair: a lone figure by the sea, twice.
    plan, answers = plan_with(MOTHER_DIRECTOR, writer_reply(SUNRISE_WALK), writer_reply(SUNRISE_WALK),
                              quote=MOTHER, director=True)
    assert len(answers.prompts) == 3 and "the quote names a mother" in answers.prompts[2]
    assert plan["generation_source"] == "gemini"  # never sent to the scene library
    assert plan["checks"]["passed"] is False
    assert any(issue.startswith("Part 1 doesn't show the mother the quote names — use Retry with Gemini")
               and "'a mother and child'" in issue for issue in plan["checks"]["issues"])
    # The page shows what is filmed, and the lost subject is the issue, not just a warning.
    assert plan["creative_direction"]["scene"] == fp._filmed_scene(plan["shots"][0]["prompt"])
    assert "lone figure" in plan["creative_direction"]["scene"]
    assert not any("films a different scene" in warning for warning in plan["checks"]["warnings"])


def test_a_repair_that_brings_the_mother_back_passes():
    plan, answers = plan_with(MOTHER_DIRECTOR, writer_reply(SUNRISE_WALK), writer_reply(MOTHER_WALK),
                              quote=MOTHER, director=True)
    assert len(answers.prompts) == 3
    assert plan["checks"]["passed"] is True and "mother and her small child" in plan["shots"][0]["prompt"]
    assert "mother" in plan["creative_direction"]["scene"]


def test_another_scene_without_a_named_subject_is_a_warning_for_the_creator():
    sailboat = director_reply(scene="A small sailboat glides across a calm lake at golden hour, its sail rippling.")
    plan, _ = plan_with(sailboat, writer_reply(BENCH), writer_reply(BENCH), quote=HOPEFUL, director=True)
    assert plan["checks"]["passed"] is True
    assert "Part 1 films a different scene from the one chosen for this quote; check it fits before generating." \
        in plan["checks"]["warnings"]


def test_the_library_is_not_judged_on_a_subject_it_cannot_film():
    assert offline(MOTHER)["checks"]["passed"] is True


def test_a_plan_that_failed_its_checks_is_still_saved(tmp_path):
    from win_engine.feedback.history_store import HistoryStore
    from win_engine.generation import ai_shorts

    history = HistoryStore(str(tmp_path / "ai-shorts.db"))
    failed = offline(MOTHER)
    failed["checks"] = {"passed": False, "issues": fp.subject_issues(MOTHER, SUNRISE_WALK), "warnings": []}

    def package(script, research, context=None):
        run_id = research["history_store"].record_analysis_run(
            query=script, intent="emotional", content_angle="quote", title="A title #shorts", title_score=80.0,
            retention_risk="low", opportunity_label="UNMEASURED", opportunity_score=None,
            payload={"title": "A title #shorts"},
        )
        return {"title": "A title #shorts", "history_run_id": run_id, "research_warnings": []}

    with patch.object(ai_shorts, "_plan_flow_shots", return_value=failed), \
            patch.object(ai_shorts, "generate_seo_suggestions", side_effect=package), \
            patch.object(gemini_client, "is_available", return_value=False):
        saved = ai_shorts.generate_ai_short(history, quote=MOTHER, parts=2)
    assert isinstance(saved["id"], int) and saved["checks"]["passed"] is False
    assert saved["checks"]["issues"][0].startswith("Part 1 doesn't show the mother")


# ---------------------------------------------------------------------------
# External review: the scene library shows what the quote names, and is judged on it
# ---------------------------------------------------------------------------


def test_without_gemini_a_mother_quote_gets_a_mother_and_child_scene_that_passes():
    # The reviewer's case: Gemini unavailable gave a wooden jetty over water and still passed.
    for parts in (1, 2, 3):
        plan = offline(MOTHER, parts=parts)
        assert plan["generation_source"] == "fallback" and plan["checks"]["passed"] is True, parts
        assert "mother" in plan["shots"][0]["prompt"] and "child" in plan["shots"][0]["prompt"]
        assert "jetty" not in plan["shots"][0]["prompt"]
        assert fp.missing_subjects(MOTHER, plan["shots"][0]["prompt"]) == []
    assert offline(MOTHER)["mood"]["visual_metaphor"].startswith("a mother and child walking hand in hand")
    assert "father and" in offline("My father never said much, but he was always there.")["shots"][0]["prompt"]


@pytest.mark.parametrize("quote, words", [
    ("Stars can't shine without darkness.", "star"),
    ("After every storm the sky clears.", "storm"),
    ("A real friend walks in when the rest walk out.", "friends"),
    ("The mountains are calling and I must go.", "mountain"),
])
def test_without_gemini_named_imagery_and_relationships_get_their_own_scene(quote, words):
    plan = offline(quote, parts=2)
    assert words in plan["shots"][0]["prompt"].casefold() and plan["checks"]["passed"] is True


def test_a_subject_the_library_cannot_also_show_fails_with_an_honest_message():
    plan = offline("My mother taught me to love the stars.")
    assert plan["checks"]["passed"] is False
    assert "Gemini was unavailable, so this built-in scene doesn't show the stars the quote names — use Retry with Gemini" \
        in plan["checks"]["issues"]


def test_a_sad_relationship_quote_keeps_the_dusk_light_in_the_library():
    sad = fp.fallback_shot(MOTHER, 1, 1, "family love", tone="sad")["prompt"]
    warm = fp.fallback_shot(MOTHER, 1, 1, "family love", tone="romantic")["prompt"]
    assert "blue dusk" in sad and "blue dusk" not in warm


def test_quotes_without_a_named_subject_keep_their_library_scene():
    assert fp.library_feeling(QUOTE_PLAIN)[0] == "being misunderstood"
    assert offline(QUOTE_PLAIN)["mood"]["feeling"] == "being misunderstood"


QUOTE_PLAIN = "Stop explaining yourself to people who already decided to misunderstand you"


@pytest.mark.parametrize("quote, borrowed", [
    ("The sea always brings me back to myself.", "love unreturned"),
    ("Some people feel the rain, others just get wet.", "being misunderstood"),
    ("Autumn shows us how lovely it is to let things go.", "change and endings"),
])
def test_a_borrowed_library_scene_does_not_lend_its_label(quote, borrowed):
    from win_engine.generation.ai_shorts_seo import local_tone

    plan = offline(quote)
    assert plan["mood"]["visual_metaphor"] == fp._scene_for(borrowed).metaphor  # the borrowed scene is used
    label = fp._TONE_LABELS.get(local_tone(quote), "reflective")
    assert plan["mood"]["feeling"] == label != borrowed
    assert plan["mood"]["keywords"][0] == label
    assert plan["checks"]["passed"] is True


def test_a_quote_whose_own_words_chose_the_scene_keeps_its_label():
    # No named subject: the lexicon's feeling and label stand.
    plan = offline("I loved you in the only way I knew and it was never enough for you")
    assert plan["mood"]["feeling"] == "love unreturned"
    assert offline(MOTHER)["mood"]["feeling"] == "family love"  # a subject's own scene keeps its own label


# ---------------------------------------------------------------------------
# Love that hurts is the pain's tone, filmed with the pain's intensity
# ---------------------------------------------------------------------------

LOVE_KILLS = "There are plenty of ways to die, but only love can kill and keep you alive to feel it."
MEADOW = (
    "Wide shot, slow push-in on a 35mm lens, vertical 9:16 portrait composition, one continuous 8-second shot. "
    "A wide meadow fills the lower third, tall grass swaying gently in a peaceful warm golden glow at sunset. "
    "Cinematic natural light; the upper-middle stays calm and soft. " + CLOSING
)


def love_reply(quote_meaning: str, *, tone: str = "romantic", **overrides) -> str:
    return director_reply(
        quote_meaning=quote_meaning, emotion=None, tone=tone,
        scene="A wide-open meadow at golden hour with tall grass slowly bending in the wind under a warm, soft sky.",
        candidates=["A wide-open meadow at golden hour with tall grass bending in the wind.",
                    "A lone figure walks along an empty seawall at night as the wind pulls at their coat.",
                    "A couple watches a warm sunset on a beach."],
        **overrides,
    )


def test_love_that_kills_is_heartbroken_and_a_warm_meadow_costs_the_repair():
    reply = love_reply("The immense emotional intensity of love is capable of causing deep, consuming pain, yet it "
                       "makes a person feel most alive in the process.")
    plan, answers = plan_with(reply, writer_reply(MEADOW), writer_reply(NIGHT_WALK), quote=LOVE_KILLS, director=True)
    assert plan["creative_direction"]["tone"] == plan["quote_understanding"]["tone"] == "heartbroken"
    # The candidate that already carries the pain becomes the scene.
    assert plan["creative_direction"]["scene"].startswith("A lone figure walks along an empty seawall at night")
    writer_prompt, repair_prompt = answers.prompts[1], answers.prompts[2]
    assert "Correction to the direction: the quote holds love together with pain, so the tone is heartbroken" in writer_prompt
    assert "no peaceful warm landscape" in writer_prompt
    assert len(answers.prompts) == 3 and "filmed as peaceful warmth" in repair_prompt
    assert "at night" in plan["shots"][0]["prompt"] and plan["checks"]["passed"] is True
    assert any("its meaning is pain; the plan uses heartbroken" in warning for warning in plan["checks"]["warnings"])


def test_a_peaceful_pain_prompt_the_repair_cannot_fix_stays_a_warning():
    reply = love_reply("Love causes deep, consuming pain.")
    plan, _ = plan_with(reply, writer_reply(MEADOW), writer_reply(MEADOW), quote=LOVE_KILLS, director=True)
    assert plan["generation_source"] == "gemini"
    assert any("filmed as peaceful warmth" in warning for warning in plan["checks"]["warnings"])


@pytest.mark.parametrize("quote, meaning, tone, expected", [
    ("Home is not a place, it's a person.", "Home is the person you love and belong with.", "romantic", "romantic"),
    (HEALED, "After heartbreak, the heart healed quietly without being noticed.", "healing", "healing"),
    ("I loved you more than you loved me.", "Loving someone more than they love you leaves a quiet, lasting hurt.",
     "romantic", "heartbroken"),
])
def test_the_tone_follows_the_meaning(quote, meaning, tone, expected):
    plan, _ = plan_with(love_reply(meaning, tone=tone), writer_reply(NIGHT_WALK), writer_reply(NIGHT_WALK),
                        quote=quote, director=True)
    assert plan["quote_understanding"]["tone"] == expected


def test_pain_that_is_over_keeps_the_directors_tone():
    assert fp.pain_tone("Love again.", {"tone": "romantic", "quote_meaning": "After the heartbreak, new love feels safe."}) is None
    assert fp.pain_tone("A quiet ache.", {"tone": "calm", "quote_meaning": "A quiet ache that will not leave."}) == "bittersweet"
    assert fp.pain_tone("x", {"tone": "hopeful", "quote_meaning": "Pain makes you stronger."}) is None


def test_pain_tones_always_get_a_person_in_the_frame():
    for tone in ("heartbroken", "sad", "lonely", "numb", "angry", "anxious"):
        assert not any("no person at all" in fp._composition(f"quote {n}", [], tone) for n in range(24)), tone
    assert any("no person at all" in fp._composition(f"quote {n}", [], "calm") for n in range(24))


def test_an_over_long_emotion_keeps_its_first_six_words():
    assert fp.direction_emotion("a very long single clause of more than six words") == "a very long single clause of"
