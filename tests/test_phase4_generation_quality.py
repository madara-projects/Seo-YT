from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.package_builder import build_title_thumbnail_packages
from win_engine.generation.expansion_engine import build_chapters
from win_engine.generation.strategy_engine import _content_specific_fallback
from win_engine.analysis.generation_quality import (
    apply_quality_gate,
    evaluate_package_quality,
    evidence_trace,
    focused_short_hashtags,
    has_unsupported_instructional_framing,
    normalize_unicode,
    title_copies_quote,
    title_similarity,
    unicode_words,
)
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.migrations import CURRENT_SCHEMA_VERSION, connect_managed, prepare_database
from win_engine.llm import seo_writer


DIVERSE_BRIEFS = [
    ("solar cooking", "How a Cardboard Solar Oven Cooked Rice"),
    ("rainy quote", "Did I Deserve More Than the Bare Minimum?"),
    ("python tutorial", "Parse a CSV Safely in Python in Three Steps"),
    ("budget travel", "What Rs 500 Buys on a Chennai Day Trip"),
    ("phone review", "Pixel Battery After 30 Days of Real Use"),
    ("fitness form", "Fix Your Squat Depth Without Adding Weight"),
    ("dosa recipe", "Crisp Dosa Batter Using a Simple Fermentation Test"),
    ("gaming", "The Final Move That Saved This Ranked Match"),
    ("study", "A 20 Minute Revision Method for Dense Chapters"),
    ("camera", "Why This Window Light Makes Interviews Look Softer"),
    ("gardening", "Rescue Basil Leaves Before the Roots Start Rotting"),
    ("music", "Building a Lo-Fi Beat From One Recorded Train Sound"),
    ("finance", "Where My Monthly Grocery Budget Actually Went"),
    ("history", "How This Forgotten Bridge Changed a Trade Route"),
    ("drawing", "Shade a Realistic Eye With Only One Pencil"),
    ("productivity", "I Removed Notifications for Seven Honest Days"),
    ("cycling", "What I Packed for a 100 Kilometre Ride"),
    ("pet care", "Teach a Rescue Dog to Trust the Doorway"),
    ("language", "Five Tamil Phrases I Use at the Market"),
    ("woodwork", "Cut a Clean Dovetail With a Hand Saw"),
    ("science", "Watch Salt Crystals Grow Across Seven Days"),
    ("makeup", "A Humidity Proof Base Tested on a Commute"),
    ("book review", "The Chapter That Changed How I Read Failure"),
    ("car repair", "Find a Battery Drain With a Multimeter"),
    ("meditation", "A Two Minute Breathing Reset Before Work"),
    ("street food", "Inside a Midnight Parotta Stall in Madurai"),
    ("coding", "The Race Condition Hidden in This Async Function"),
    ("home repair", "Stop a Leaking Tap Without Replacing the Sink"),
    ("photography", "Freeze Rain Drops Using Manual Camera Settings"),
    ("documentary", "One Fisherman's Morning Before the City Wakes"),
]


def valid_package(title: str = "Did I Deserve More Than the Bare Minimum? 💔 #shorts") -> dict:
    quote = "Didn't I at least deserve the bare minimum from them?"
    return {
        "title": title,
        "variants": [title, "The Question I Could Never Ask Them 🌧️ #shorts"],
        "description": f'"{quote}" A rainy-road quote Short that preserves the creator\'s exact question.',
        "tags": ["bare minimum quote", "rainy road quote", "shorts"],
        "hashtags": ["#Shorts", "#Quotes", "#SelfWorth"],
    }


class Phase4QualityTests(unittest.TestCase):
    def test_friendship_boundary_quote_requires_title_to_include_the_turn(self):
        quote = "Wdym?? The one who poured heart and Soul into friendship is now setting boundaries???"
        package = valid_package("When you put your heart and soul into friendship 🌿 #shorts")
        package["description"] = quote + " A reflection on setting boundaries in friendship."
        gate = evaluate_package_quality(package, script=quote, creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"})
        rejected = {item["code"] for row in gate["rejected_candidates"] for item in row["issues"]}
        # The payoff check replaced the "central terms" overlap rule.
        self.assertIn("missing_quote_payoff", rejected)

    def test_friendship_quote_rejects_awkward_idiom_and_invented_causality(self):
        quote = "The one who poured heart and soul into friendship is now setting boundaries."
        package = valid_package("When heart and soul friendship leads to setting boundaries #shorts")
        package["description"] = quote + " A reflection on friendship boundaries."
        gate = evaluate_package_quality(package, script=quote, creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"})
        rejected = {item["code"] for row in gate["rejected_candidates"] for item in row["issues"]}
        self.assertIn("unnatural_title_phrase", rejected)
        self.assertIn("invented_causality", rejected)

    def test_quote_description_rejects_generic_exploration_and_invented_one_sided_dynamic(self):
        quote = "The one who poured heart and soul into friendship is now setting boundaries."
        package = valid_package("Setting Boundaries After Giving Your All 🌿 #shorts")
        package["description"] = quote + " This short explores friendship dynamics and one-sided effort."
        gate = evaluate_package_quality(package, script=quote, creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"})
        codes = {item["code"] for item in gate["issues"]}
        self.assertIn("generic_description_filler", codes)
        self.assertIn("invented_relationship_dynamic", codes)

    def test_quote_explainer_phrases_are_instructional_framing(self):
        self.assertTrue(has_unsupported_instructional_framing("Understanding grief"))
        self.assertTrue(has_unsupported_instructional_framing("Exploring the shape of absence"))
        self.assertFalse(has_unsupported_instructional_framing("Why silence feels heavy during grief"))

    def test_quote_package_rejects_an_invented_person_being_gone(self):
        quote = "Grief teaches you the weight of silence and the shape of absence."
        package = {
            "title": "Silence in grief when someone is gone 🕯️ #shorts",
            "variants": ["Silence in grief when someone is gone 🕯️ #shorts"],
            "description": f'"{quote}" A reflection on grief, silence, and absence.',
            "tags": ["grief quotes", "yt", "shorts"],
            "hashtags": ["#shorts", "#Grief"],
        }
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"},
        )
        rejected_codes = {
            issue["code"] for item in gate["rejected_candidates"] for issue in item["issues"]
        }
        self.assertIn("invented_loss_event", rejected_codes)

        package["title"] = "Being forgotten by someone you remember 💭 #shorts"
        package["variants"] = [package["title"]]
        package["description"] = "A memory that stays in your mind after they have gone."
        gate = evaluate_package_quality(package, script="Being forgotten by someone you remember.", creator_brief={"video_format": "youtube_shorts"})
        self.assertIn("invented_loss_event", {item["code"] for item in gate["issues"]})

    def test_short_hashtags_are_followed_labels_not_coined_phrases(self):
        # New contract: at most one compound hashtag, never longer than three
        # words; a quote Short leads with #quotes and its feeling's hashtag.
        self.assertEqual(focused_short_hashtags(["letting go of the wrong person", "yt", "shorts"]), ["#shorts"])
        self.assertEqual(
            focused_short_hashtags(["painful contradiction", "seeking comfort", "yt", "shorts"]),
            ["#shorts", "#PainfulContradiction"],
        )
        # A heart is not a broken one: the feeling here is missing someone.
        self.assertEqual(
            focused_short_hashtags(["painful contradiction"], quote="My heart still misses you."),
            ["#shorts", "#quotes", "#missingyou"],
        )
        self.assertEqual(
            focused_short_hashtags(["painful contradiction"], quote="My heart is broken, but I still smile."),
            ["#shorts", "#quotes", "#heartbreak"],
        )
        self.assertEqual(
            focused_short_hashtags(["being forgotten"], quote="Some people only value you when they need you."),
            ["#shorts", "#quotes", "#BeingForgotten"],
        )

    def test_green_requires_average_subject_tag_score_of_72(self):
        def judged(score, video_format, title):
            package = valid_package(title)
            package["variants"] = [title]
            package["tags"] = ["bare minimum quote", "one sided effort", "emotional hurt"]
            evidence = {
                "selected_keywords": [
                    {
                        "keyword": tag, "classification": "secondary_topic", "source_classification": "combined",
                        "source_support_score": 85, "source_support": "creator-source support",
                        "keyword_relevance_score": score,
                    }
                    for tag in package["tags"]
                ]
            }
            gate = evaluate_package_quality(
                package,
                script='Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts',
                creator_brief={"creator_intent": "A reflection on one-sided effort and emotional hurt.",
                               "video_format": video_format},
                tag_evidence=evidence,
            )
            return gate, {item["code"]: item["severity"] for item in gate["final_seo_quality"]["warnings"]}

        gate, notes = judged(70, "story", "Did I Deserve More Than the Bare Minimum?")
        self.assertEqual(gate["verdict"], "YELLOW")
        self.assertEqual(notes["weak_tag_usefulness"], "warning")
        # Tags play a minimal role in a Short's discovery: the weak score is
        # reported, but it does not decide the Short's verdict.
        weak, notes = judged(70, "youtube_shorts", "Did I Deserve More Than the Bare Minimum? 💔 #shorts")
        strong, _ = judged(95, "youtube_shorts", "Did I Deserve More Than the Bare Minimum? 💔 #shorts")
        self.assertEqual(notes["weak_tag_usefulness"], "info")
        self.assertEqual(weak["verdict"], strong["verdict"])

    def test_unquoted_quote_marker_is_separated_from_visual_direction(self):
        brief = build_creator_brief(
            script=(
                "the quote is- You don't give up overnight on someone. You reach a point "
                "where your heart quietly says, Enough and the background of the video is "
                "rainy weather, someone holding a cup of tea by a window"
            )
        )
        self.assertEqual(
            brief["exact_quote"],
            "You don't give up overnight on someone. You reach a point where your heart quietly says, Enough",
        )
        # Prose ("the background of the video is ...") is not a "Background:"
        # label, so no visual requirement is inferred from it.
        self.assertEqual(brief["visual_requirements"], "")
        self.assertNotIn("background", brief["exact_quote"].casefold())
        self.assertTrue(brief["topic"].startswith("you don't give up overnight"))

    def test_malformed_input_marker_title_is_rejected(self):
        package = valid_package("How to is- you don't give overnight someone reach point #shorts")
        gate = evaluate_package_quality(package, script="A quote Short about knowing when to let go")
        codes = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("malformed_title_fragment", codes)

    def test_shorts_never_receive_synthetic_chapters(self):
        chapters = build_chapters(
            "A reflective quote Short",
            {"video_format": "youtube_shorts", "duration_seconds": 20},
        )
        self.assertEqual(chapters, [])

    def test_latest_broken_input_has_natural_fallback_package(self):
        source = (
            'the quote is- You don\'t give up overnight on someone. You reach a point where '
            'your heart quietly says, "Enough and the background of the video is rainy weather, '
            'someone holding a cup of tea by a window'
        )
        brief = build_creator_brief(script=source)
        package = _content_specific_fallback(brief["topic"], [], brief)
        combined = " ".join([package["title"], package["description"], *package["tags"]]).casefold()
        self.assertNotIn("how to is-", combined)
        self.assertNotIn("background of the video is", package["description"].casefold())
        # The quote is too long to keep whole, so the title is its punchline
        # sentence, uncut; "You don't give up overnight on someone" alone
        # stops before the point.
        self.assertTrue(package["title"].startswith("You reach a point where your heart quietly says, Enough"))
        self.assertNotIn("…", package["title"])
        self.assertNotIn("#shorts", package["title"].casefold())
        self.assertIn("you don't give up overnight on someone", package["description"].casefold())
        # "enough" in a quote no longer adds the stock tag "knowing when to let go".
        self.assertNotIn("knowing when to let go", package["tags"])

    def test_silence_quote_fallback_is_a_complete_human_package(self):
        quote = "at the end, it's only me and the silence that knows everything.."
        brief = build_creator_brief(
            script=quote,
            video_format="youtube_shorts",
            exact_quote=quote,
            on_screen_text=quote,
            visual_requirements="One person walking alone in quiet streets.",
            creator_intent="A reflective Short about solitude, silence, and private thoughts.",
        )
        package = _content_specific_fallback(brief["topic"], [], brief)
        # The title, tags and hashtags come from the creator's words. Five titles,
        # "#DeepThoughts #Solitude", "inner silence" and "SILENCE KNOWS" were
        # written for this test quote and given to any quote about silence.
        self.assertTrue(package["title"].casefold().startswith("at the end, it's only me and the silence "))
        # New contract: #shorts is never injected into a title; the hashtags
        # are #shorts, #quotes and the hashtag of the feeling the quote names.
        self.assertNotIn("#shorts", package["title"].casefold())
        # A Short's viewers are watching the street; the description does not narrate it.
        self.assertNotIn("A lone person walks", package["description"])
        self.assertNotIn("A One person", package["description"])
        self.assertNotIn("inner silence", package["tags"])
        self.assertEqual(package["hashtags"], ["#shorts", "#quotes", "#silence"])

        title_rows = [{"title": title, "package_intent": "Browse"} for title in package["variants"]]
        choices = build_title_thumbnail_packages(title_rows, brief, validated=True)
        self.assertNotEqual(choices[0]["thumbnail_text"], "SILENCE KNOWS")
        self.assertIn("walking alone", choices[0]["thumbnail_visual"].casefold())
        self.assertNotEqual(choices[0]["viewer_promise"], "A clear, truthful reason to watch.")

    def test_rarity_quote_fallback_complements_quote_and_thumbnail(self):
        quote = "You deserve somebody who knows how hard it is to find somebody like you"
        brief = build_creator_brief(
            script=quote, video_format="youtube_shorts", exact_quote=quote,
            visual_requirements="One person walking alone.",
            creator_intent="A reflection about recognizing a person's rarity and worth.",
        )
        package = _content_specific_fallback(brief["topic"], [], brief)
        # "Know Your Worth—You're Hard to Replace", "being valued" and "KNOW YOUR
        # WORTH" were written for this test quote; the package uses its words.
        self.assertTrue(package["title"].startswith("You deserve somebody who knows how hard it is"))
        self.assertNotIn("being valued", package["tags"])
        choices = build_title_thumbnail_packages(
            [{"title": title} for title in package["variants"]], brief, validated=True,
        )
        self.assertNotEqual(choices[0]["thumbnail_text"], "KNOW YOUR WORTH")

    def test_full_quote_title_is_allowed_beside_complementary_titles_but_a_cut_one_is_not(self):
        # New contract: the whole quote (or its punchline clause) may be
        # option 1; a copy cut with "…" never passes.
        quote = "You deserve somebody who knows how hard it is to find somebody like you"
        copied = quote + " ✨ #shorts"
        cut = "You deserve somebody who knows how hard it is to find... 🌙 #shorts"
        package = {
            "title": copied,
            "variants": [copied, "Know Your Worth—You're Hard to Replace ✨ #shorts", "You're Rarer Than You Realize 🤍 #shorts", cut],
            "description": f'“{quote}”\n\nA reflection about recognizing your worth.',
            "tags": ["know your worth", "being valued", "hard to replace"],
            "hashtags": ["#shorts", "#KnowYourWorth"],
        }
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts", "creator_intent": "recognizing your worth"},
            enforce_final_tag_rules=False,
        )
        rejected = {item["title"]: {reason["code"] for reason in item["issues"]} for item in gate["rejected_candidates"]}
        self.assertNotIn(copied, rejected)
        self.assertEqual(gate["accepted_candidates"][0]["title"], copied)
        self.assertIn("quote_title_cut", rejected[cut])
        self.assertTrue(title_copies_quote(cut, quote))
        # Alternatives in new words keep the quote-led package from the
        # "every title repeats the quote" warning.
        self.assertNotIn("title_duplicates_on_screen_quote", {item["code"] for item in gate["warnings"]})

    def test_semantically_proven_worth_tags_pass_final_grounding(self):
        quote = "You deserve somebody who knows how hard it is to find somebody like you"
        tags = ["being valued", "genuine appreciation", "rare personal qualities"]
        evidence = {
            "selected_keywords": [
                {"keyword": tag, "source_support_score": 80, "source_classification": "combined", "source_support": "rarity-and-worth semantic bridge", "keyword_relevance_score": 75}
                for tag in tags
            ]
        }
        package = {
            "title": "Know Your Worth—You're Hard to Replace ✨ #shorts",
            "variants": ["Know Your Worth—You're Hard to Replace ✨ #shorts"],
            "description": f'“{quote}”\n\nA reflection about recognizing your worth.',
            "tags": tags,
            "hashtags": ["#shorts", "#KnowYourWorth"],
        }
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts", "creator_intent": "recognizing personal rarity and worth"},
            tag_evidence=evidence,
        )
        self.assertNotIn("unrelated_tag", {item["code"] for item in gate["issues"]})
        self.assertTrue(gate["passed"])


    def test_structured_brief_has_truthful_provenance_and_completeness(self):
        brief = build_creator_brief(script='Rainy road. On-screen quote: "Keep going."')
        self.assertEqual(brief["field_provenance"]["target_audience"]["source"], "unknown")
        self.assertEqual(brief["field_provenance"]["exact_quote"]["source"], "inferred")
        self.assertLess(brief["completeness"], 100)
        self.assertIn("target_audience", brief["missing_fields"])

    def test_creator_supplied_is_not_confused_with_inferred(self):
        brief = build_creator_brief(script="A repair tutorial", target_audience="New homeowners", video_format="tutorial")
        self.assertEqual(brief["field_provenance"]["target_audience"]["source"], "creator_supplied")
        self.assertEqual(brief["field_provenance"]["topic"]["source"], "inferred")

    def test_duplicate_candidate_is_rejected_and_not_padded(self):
        package = valid_package()
        package["variants"] = [package["title"], "Did I Really Deserve More Than the Bare Minimum?"]
        gate = evaluate_package_quality(package, script='Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts')
        cleaned = apply_quality_gate(package, gate)
        self.assertLess(len(cleaned["variants"]), 3)
        self.assertTrue(any(item["code"] == "fewer_legitimate_alternatives" for item in gate["warnings"]))

    def test_exact_quote_title_and_one_tag_cannot_be_green(self):
        quote = "At the end, it's only me and the silence that knows everything."
        package = {
            "title": quote + " #shorts",
            "variants": [quote + " #shorts"],
            "description": f'“{quote}” A reflective moment about silence.',
            "tags": ["inner silence"],
            "hashtags": ["#shorts"],
        }
        gate = evaluate_package_quality(
            package,
            script=quote,
            creator_brief={
                "exact_quote": quote,
                "video_format": "youtube_shorts",
                "visual_requirements": "One person walking alone in quiet streets.",
                "creator_intent": "A reflective Short about solitude and private thoughts.",
            },
        )
        self.assertEqual(gate["verdict"], "YELLOW")
        warning_codes = {item["code"] for item in gate["warnings"] + gate["final_seo_quality"]["warnings"]}
        self.assertIn("title_duplicates_on_screen_quote", warning_codes)
        self.assertIn("sparse_tag_set", warning_codes)

    def test_two_strong_subject_tags_do_not_trigger_padding_warning(self):
        quote = "The worst feeling is being forgotten by someone you cannot forget."
        package = {
            "title": "Why Being Forgotten Hurts So Much #shorts",
            "variants": ["Why Being Forgotten Hurts So Much #shorts"],
            "description": f'“{quote}” A reflection on remembering someone who has forgotten you.',
            "tags": ["being forgotten", "painful memories", "yt", "shorts"],
            "hashtags": ["#BeingForgotten", "#PainfulMemories", "#Shorts"],
        }
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts", "visual_requirements": "walking", "creator_intent": "reflection"},
            tag_evidence={"selected_keywords": [
                {"keyword": "being forgotten", "score": 96, "source_support_score": 90},
                {"keyword": "painful memories", "score": 94, "source_support_score": 85},
            ]},
        )
        warning_codes = {item["code"] for item in gate["final_seo_quality"]["warnings"]}
        self.assertNotIn("sparse_tag_set", warning_codes)

    def test_broken_article_description_is_rejected(self):
        package = valid_package()
        package["description"] = "A One person walking alone is the visual."
        gate = evaluate_package_quality(package, script="A quote Short about walking alone")
        self.assertIn("broken_description_grammar", {item["code"] for item in gate["issues"]})

    def test_quote_package_cannot_invent_night_darkness_or_comfort(self):
        quote = "At the end, it's only me and the silence that knows everything."
        package = {
            "title": "Finding Comfort on Empty Streets at Night 🌙 #shorts",
            "variants": ["Thinking Out Loud While Walking in the Dark 🌌 #shorts"],
            "description": f'“{quote}” A peaceful moment of healing and comfort.',
            "tags": ["silence"],
            "hashtags": ["#shorts"],
        }
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts", "visual_requirements": "A person walking alone in streets."},
        )
        rejected_codes = {reason["code"] for row in gate["rejected_candidates"] for reason in row["issues"]}
        self.assertIn("unsupported_context", rejected_codes)
        self.assertIn("unsupported_action", rejected_codes)
        self.assertIn("unsupported_context", {item["code"] for item in gate["issues"]})

    def test_quote_package_cannot_invent_romance_or_that_someone_moved_on(self):
        quote = "The worst feeling is being forgotten by someone you cannot forget."
        package = valid_package()
        package["description"] = (
            f'"{quote}" The person has moved on from your life, leaving forgotten love behind.'
        )
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"},
        )
        codes = {item["code"] for item in gate["issues"]}
        self.assertIn("unsupported_context", codes)
        self.assertIn("invented_story_detail", codes)

    def test_live_moved_on_wording_is_rejected_in_title_and_description(self):
        quote = "The worst feeling is not being lonely; it's being forgotten by someone you can't forget."
        package = valid_package("When you can't forget a person who moved on 💭 #shorts")
        package["description"] = "A heavy memory while the other person has moved on. A reflection on unrequited memory."
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"},
        )
        codes = {item["code"] for item in gate["issues"]}
        rejected_codes = {item["code"] for row in gate["rejected_candidates"] for item in row["issues"]}
        self.assertIn("invented_story_detail", codes | rejected_codes)
        self.assertIn("unsupported_context", codes)

    def test_unicode_normalization_preserves_emoji_joiners(self):
        self.assertEqual(normalize_unicode("Walking 🚶‍♂️"), "Walking 🚶‍♂️")

    def test_quote_fidelity_failure_is_structured(self):
        package = valid_package()
        package["description"] = "A generic emotional quote without the original words."
        gate = evaluate_package_quality(package, script='Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts')
        self.assertFalse(gate["passed"])
        self.assertIn("quote_fidelity", {item["code"] for item in gate["issues"]})

    def test_unsupported_relationship_is_rejected(self):
        package = valid_package("They Left Because I Asked for the Bare Minimum")
        gate = evaluate_package_quality(package, script='Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts')
        codes = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("relationship_event", codes)

    def test_creator_preferred_yt_and_shorts_tags_are_kept_but_platform_filler_is_dropped(self):
        # New contract: tags are advisory. Filler is noted and dropped from
        # the package; it never fails it.
        package = valid_package()
        package["tags"] = ["bare minimum quote", "yt", "shorts", "youtube shorts"]
        gate = evaluate_package_quality(package, script="A quote Short")
        self.assertNotIn("platform_tag_filler", {item["code"] for item in gate["issues"]})
        filler = {item["tag"] for item in gate["warnings"] if item["code"] == "platform_tag_filler"}
        self.assertEqual(filler, {"youtube shorts"})
        self.assertEqual(apply_quality_gate(package, gate)["tags"], ["bare minimum quote", "yt", "shorts"])

    def test_short_title_shorts_hashtag_is_optional_but_never_duplicated(self):
        # New contract: YouTube detects a Short by its format, so a title
        # without #shorts passes; an emoji for the quote's feeling is only suggested.
        missing = valid_package("Did I Deserve More Than the Bare Minimum?")
        gate = evaluate_package_quality(
            missing,
            script='A rainy quote Short: "Didn\'t I at least deserve the bare minimum from them?"',
        )
        rejected = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertNotIn("missing_shorts_title_hashtag", rejected)
        self.assertIn("Did I Deserve More Than the Bare Minimum?", [item["title"] for item in gate["accepted_candidates"]])
        self.assertIn("missing_contextual_title_emoji", {item["code"] for item in gate["warnings"]})

        duplicated = valid_package("Did I Deserve More? 💔 #shorts #Shorts")
        gate = evaluate_package_quality(duplicated, script="A rainy quote Short")
        rejected = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("duplicate_shorts_title_hashtag", rejected)

    def test_non_short_title_does_not_accept_shorts_label(self):
        package = {
            "title": "How to Parse a CSV Safely #shorts",
            "variants": ["How to Parse a CSV Safely #shorts"],
            "description": "A practical CSV parsing tutorial.",
            "tags": ["csv parsing tutorial"],
            "hashtags": [],
        }
        gate = evaluate_package_quality(package, script="A long-form CSV parsing tutorial")
        rejected = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("unexpected_shorts_title_hashtag", rejected)

    def test_repeated_emoji_template_is_rejected_from_recent_history(self):
        package = valid_package()
        gate = evaluate_package_quality(
            package,
            script='A rainy quote Short: "Didn\'t I at least deserve the bare minimum from them?"',
            recent_titles=["First reflection 💔 #shorts", "Second reflection 💔 #shorts", "Third reflection 💔 #shorts"],
        )
        rejected = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("repeated_emoji_template", rejected)

    def test_tamil_and_tanglish_unicode_validation(self):
        tamil = {"title": "மழையில் ஒரு நினைவு", "variants": ["மழையில் ஒரு நினைவு"], "description": "மழையில் தோன்றிய ஒரு உண்மையான நினைவு.", "tags": ["மழை காட்சி"], "hashtags": []}
        self.assertTrue(evaluate_package_quality(tamil, script="மழை காட்சி", language="tamil")["passed"])
        tanglish = {"title": "Mazhaiyil vandha oru ninaivu", "variants": ["Mazhaiyil vandha oru ninaivu"], "description": "Indha mazhai oru pazhaya ninaivai thirumba kondu vandhadhu.", "tags": ["rain quote"], "hashtags": []}
        self.assertTrue(evaluate_package_quality(tanglish, script="Rain visual", language="tanglish")["passed"])
        self.assertTrue(unicode_words("தமிழ் mixed English"))

    def test_recent_title_similarity_rejects_repetition(self):
        package = {"title": "A Better Way to Plan a Chennai Day Trip", "variants": ["A Better Way to Plan a Chennai Day Trip"], "description": "Plan a Chennai day trip.", "tags": ["chennai day trip"], "hashtags": []}
        gate = evaluate_package_quality(package, script="Plan a Chennai day trip", recent_titles=["A Better Way to Plan Your Chennai Day Trip"])
        codes = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("recent_title_repetition", codes)

    def test_insufficient_evidence_is_not_personalized(self):
        trace = evidence_trace({"cohort": {"sample_size": 4, "learning_allowed": False}})
        self.assertFalse(trace["learning_allowed"])
        self.assertEqual(trace["status"], "insufficient_evidence")

    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=True)
    @patch("win_engine.llm.seo_writer.generate_one")
    def test_one_repair_maximum(self, mocked_generate, _available):
        broken = valid_package("They Left Because I Asked for More")
        broken["description"] += " They left after I asked for more."
        repaired = valid_package()
        mocked_generate.side_effect = [broken, repaired]
        packages, source = seo_writer.write_multilang_packages_with_source(
            'Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts', languages=["english"]
        )
        self.assertEqual(mocked_generate.call_count, 2)
        self.assertEqual(source, "gemini")
        self.assertTrue(packages["english"]["generation_trace"]["repair_succeeded"])

    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=True)
    @patch("win_engine.llm.seo_writer.generate_one")
    def test_a_short_title_without_shorts_hashtag_needs_no_repair(self, mocked_generate, _available):
        # New contract: #shorts in a title is optional, so its absence is no
        # reason to spend a repair call, and it is never injected.
        written = valid_package("Did I Deserve More Than the Bare Minimum?")
        written["variants"] = ["Did I Deserve More Than the Bare Minimum?", "The Question I Could Never Ask Them"]
        mocked_generate.side_effect = [written, valid_package()]
        packages, source = seo_writer.write_multilang_packages_with_source(
            'A rainy quote Short: "Didn\'t I at least deserve the bare minimum from them?"',
            languages=["english"],
        )
        self.assertEqual(mocked_generate.call_count, 1)
        self.assertEqual(source, "gemini")
        self.assertEqual(packages["english"]["title"], "Did I Deserve More Than the Bare Minimum?")
        self.assertFalse(packages["english"]["generation_trace"]["repair_attempted"])

    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=True)
    @patch("win_engine.llm.seo_writer.generate_one")
    def test_failed_repair_retains_bounded_quality_reasons(self, mocked_generate, _available):
        broken = valid_package("They Left Because I Asked for More #shorts")
        broken["variants"] = [broken["title"]]
        mocked_generate.side_effect = [dict(broken), dict(broken)]
        packages, source = seo_writer.write_multilang_packages_with_source(
            'Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts', languages=["english"]
        )
        self.assertEqual(source, "fallback")
        self.assertIsNone(packages["english"])
        trace = seo_writer.last_generation_diagnostics()["english"]
        self.assertEqual(trace["fallback_reason"], "quality_gate_rejection")
        self.assertTrue(trace["initial_quality_rejection"]["rejected_titles"])
        self.assertTrue(trace["repair_quality_rejection"]["rejected_titles"])
        self.assertIn("gemini_quality_rejection_after_repair", trace["events"])

    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=True)
    @patch("win_engine.llm.seo_writer.generate_one", return_value=None)
    def test_empty_or_quota_result_does_not_trigger_repair(self, mocked_generate, _available):
        packages, source = seo_writer.write_multilang_packages_with_source("A video", languages=["english"])
        self.assertEqual(mocked_generate.call_count, 1)
        self.assertIsNone(packages["english"])
        self.assertEqual(source, "fallback")

    def test_thirty_brief_acceptance_fixture_is_materially_cross_topic(self):
        self.assertGreaterEqual(len(DIVERSE_BRIEFS), 30)
        titles = [title for _topic, title in DIVERSE_BRIEFS]
        self.assertEqual(len(titles), len({title.casefold() for title in titles}))
        self.assertTrue(all(title_similarity(left, right) < 0.82 for i, left in enumerate(titles) for right in titles[i + 1:]))
        self.assertFalse(any(title.casefold().startswith("the honest truth about") for title in titles))


class Phase4PersistenceTests(unittest.TestCase):
    def _record(self, store: HistoryStore) -> int:
        return store.record_analysis_run(
            "script", "SEARCH", "Authority", "Primary title", 8.0, "low", "WORKABLE", 60.0,
            payload={
                "title": "Primary title", "description": "Description", "tags": ["topic"], "hashtags": ["#Topic"],
                "selected_language": "english", "generation_quality": {"status": "pass"},
                "title_thumbnail_packages": [
                    {"package_id": "package-a", "title": "Primary title"},
                    {"package_id": "package-b", "title": "Alternative title"},
                ],
            },
        )

    def test_selected_package_persists_and_rejects_client_invention(self):
        store = HistoryStore(":memory:")
        run_id = self._record(store)
        with self.assertRaises(ValueError):
            store.select_generated_package(run_id, "invented")
        selected = store.select_generated_package(run_id, "package-b")
        self.assertEqual(selected["package"]["title"], "Alternative title")
        self.assertEqual(store.history_run(run_id)["selected_package"]["generated_package_id"], "package-b")

    def test_link_association_is_reported_without_inference(self):
        store = HistoryStore(":memory:")
        run_id = self._record(store)
        store.select_generated_package(run_id, "package-b")
        store.link_published_video(run_id, "abcdefghijk", "2026-08-20T00:00:00+00:00")
        self.assertTrue(store.package_selection(run_id)["later_associated_with_video"])

    def test_v2_to_v3_migration_is_additive_and_integral(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.db"
            store = HistoryStore(str(path))
            run_id = self._record(store)
            with connect_managed(str(path)) as connection:
                connection.execute("DROP TABLE analysis_package_selections")
                connection.execute("PRAGMA user_version = 2")
            result = prepare_database(str(path))
            self.assertEqual(result.new_version, CURRENT_SCHEMA_VERSION)
            with connect_managed(str(path)) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_runs WHERE id = ?", (run_id,)).fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
