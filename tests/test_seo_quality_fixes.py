"""Regression tests for the SEO-quality audit fixes.

Each test pins one defect found by running real scripts through the pipeline:
good AI output rejected by an over-broad gate, a broken fallback shipped in its
place, the result scored 100/100, Tamil scripts unable to keep any tag, and no
signal at all for what viewers actually search.
"""

import unittest
from unittest.mock import MagicMock, patch

import httpx

from win_engine.analysis.creator_brief import build_creator_brief, creator_topic
from win_engine.analysis.generation_quality import (
    evaluate_package_quality,
    keyword_placement,
    title_fluency_issues,
)
from win_engine.analysis.keyword_research import (
    _classify,
    _diverse_tag_selection,
    _suggestion_is_grounded,
    select_final_tags,
)
from win_engine.analysis.topic_lock import (
    expand_idea_to_script,
    force_hashtags,
    infer_category,
    normalize_risk_terms,
    source_lead_phrase,
)
from win_engine.analysis.transliteration import phonetic_key, phonetic_keys, phonetic_match, tamil_to_latin
from win_engine.generation.seo_generator import format_upload_ready_description
from win_engine.generation.strategy_engine import _content_specific_fallback, _trim_title_span
from win_engine.ingestion.search_suggest import SearchSuggestClient, demand_rank, suggestion_index

COLD_BREW = (
    "In this video I show you how to make cold brew coffee at home without any special "
    "equipment. You only need coarse ground coffee, a large mason jar, and cold water. "
    "Mix one cup of coffee grounds with four cups of water, stir, and let it steep in the "
    "fridge for 12 to 18 hours. Then strain it twice, first through a fine mesh sieve and "
    "then through a paper coffee filter. At the end I compare it side by side with regular "
    "hot brewed coffee and explain why cold brew tastes smoother and less bitter."
)
COLD_BREW_DESC = (
    "Learn how to make smooth cold brew coffee at home with just a mason jar. No special "
    "equipment needed.\n\n"
    "You need coarse ground coffee, a large mason jar and cold water. Use one cup of grounds "
    "to four cups of water and steep it in the fridge for 12 to 18 hours.\n\n"
    "Strain it twice through a fine mesh sieve and then a paper coffee filter. At the end I "
    "compare it with hot brewed coffee and explain why cold brew tastes smoother and less bitter."
)
BIRYANI = (
    "இந்த வீடியோவில் வீட்டிலேயே சுலபமாக செட்டிநாடு சிக்கன் பிரியாணி எப்படி செய்வது என்று "
    "பார்க்கலாம். பாஸ்மதி அரிசி, சிக்கன், தயிர், வெங்காயம், தக்காளி, புதினா, கொத்தமல்லி "
    "மற்றும் வீட்டில் அரைத்த செட்டிநாடு மசாலா தேவை. பிரஷர் குக்கரில் இரண்டு விசில் வைத்தால் "
    "போதும், பிரியாணி உதிரி உதிரியாக வரும்."
)
SAMSUNG = (
    "Honest review of the Samsung Galaxy S25 Ultra after 30 days of daily use. Battery easily "
    "lasts a full day and a half, the 200MP main camera is excellent in daylight but struggles "
    "in low light, and the S Pen is still the best stylus on any phone. The price in India "
    "starts at Rs 1,29,999. Is it worth upgrading from the S24 Ultra?"
)
QUOTE = "The biggest betrayal is knowing that if you didn't find out, they would have never told you."


def _gate(package, script, language="english", brief=None):
    package = {"variants": [], "tags": [], "hashtags": [], **package}
    return evaluate_package_quality(
        package, script=script, creator_brief=brief or {}, language=language,
        require_shorts_tags=False, enforce_final_tag_rules=bool(package.get("tags")),
    )


class TransliterationTests(unittest.TestCase):
    def test_sound_alike_words_match_across_scripts(self):
        pairs = [("chettinad", "செட்டிநாடு"), ("chicken", "சிக்கன்"), ("biryani", "பிரியாணி"),
                 ("basmati", "பாஸ்மதி"), ("masala", "மசாலா"), ("pressure", "பிரஷர்")]
        for english, tamil in pairs:
            with self.subTest(english=english):
                self.assertTrue(phonetic_match(english, phonetic_keys(tamil)))

    def test_meaning_is_not_matched_only_sound(self):
        # "onion" and வெங்காயம் mean the same thing but do not sound alike.
        self.assertFalse(phonetic_match("onion", phonetic_keys("வெங்காயம்")))
        self.assertFalse(phonetic_match("mutton", phonetic_keys(BIRYANI)))

    def test_transliteration_is_phonetic(self):
        self.assertEqual(tamil_to_latin("பிரியாணி"), "piriyaani")
        self.assertEqual(phonetic_key("chettinad"), phonetic_key("செட்டிநாடு"))


class CategoryAndTopicTests(unittest.TestCase):
    def test_a_cooking_tutorial_is_cooking_not_education(self):
        self.assertEqual(infer_category(COLD_BREW + " tutorial"), "cooking")

    def test_a_tamil_script_is_classified_by_its_subject(self):
        self.assertEqual(infer_category(BIRYANI + " tutorial"), "cooking")

    def test_format_word_alone_is_only_a_weak_prior(self):
        self.assertEqual(infer_category("a tutorial about something"), "education")

    def test_topic_is_a_contiguous_phrase_not_a_word_bag(self):
        brief = build_creator_brief(script=COLD_BREW, video_format="tutorial")
        topic = creator_topic(brief)
        self.assertTrue(topic.startswith("how to make cold brew coffee at home"))
        self.assertNotIn("you how make", topic)

    def test_tamil_topic_is_never_a_placeholder(self):
        topic = creator_topic(build_creator_brief(script=BIRYANI, language="tamil"))
        self.assertNotEqual(topic, "deep quote")
        self.assertIn("பிரியாணி", topic)

    def test_lead_in_filler_is_removed(self):
        self.assertEqual(
            source_lead_phrase("Hey guys, welcome back! In this video I show you how to fix a flat tyre."),
            "how to fix a flat tyre",
        )


class SourceIntegrityTests(unittest.TestCase):
    def test_ordinary_words_are_not_rewritten(self):
        text = "Five kitchen hacks, a cheat sheet, and how to avoid a phone scam."
        self.assertEqual(normalize_risk_terms(text), text)

    def test_policy_risk_phrases_are_still_rewritten(self):
        self.assertIn("free fire tricks", normalize_risk_terms("free fire hack tutorial").casefold())
        self.assertIn("official method", normalize_risk_terms("download the mod apk").casefold())

    def test_short_ideas_are_not_padded_with_invented_claims(self):
        idea = "morning habits for focus"
        self.assertEqual(expand_idea_to_script(idea), idea)


class GateAcceptsGoodCopyTests(unittest.TestCase):
    """Faithful, professionally written copy must pass. Each of these was rejected before."""

    def test_ordinary_copy_words_are_allowed_outside_reflective_content(self):
        for sentence in ("You'll love how easy it is.", "Get the ratio right.", "Great for the whole family."):
            with self.subTest(sentence=sentence):
                gate = _gate({"title": "How to Make Cold Brew Coffee at Home", "description": f"{COLD_BREW_DESC} {sentence}"}, COLD_BREW)
                self.assertTrue(gate["passed"], gate["issues"])

    def test_an_ingredient_list_is_not_a_tag_list(self):
        description = (
            "வீட்டிலேயே சுலபமாக செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி என்று பார்க்கலாம்.\n\n"
            "தேவையான பொருட்கள்: பாஸ்மதி அரிசி, சிக்கன், தயிர், வெங்காயம், தக்காளி, புதினா, கொத்தமல்லி, செட்டிநாடு மசாலா."
        )
        gate = _gate({"title": "செட்டிநாடு சிக்கன் பிரியாணி | Chettinad Chicken Biryani in Tamil", "description": description}, BIRYANI, "tamil")
        self.assertNotIn("tag_list_contamination", [issue["code"] for issue in gate["issues"]])

    def test_an_indian_price_does_not_make_a_tag_list(self):
        description = (
            "My honest Samsung Galaxy S25 Ultra review after 30 days of daily use.\n\n"
            "The battery easily lasts a full day and a half, the 200MP main camera is excellent in "
            "daylight but struggles in low light, and the S Pen is still the best stylus on any phone. "
            "In India, it starts at Rs 1,29,999."
        )
        gate = _gate({"title": "Samsung Galaxy S25 Ultra Review After 30 Days", "description": description}, SAMSUNG)
        self.assertTrue(gate["passed"], gate["issues"])

    def test_english_search_tags_are_grounded_in_a_tamil_script(self):
        gate = _gate({
            "title": "செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி",
            "description": "வீட்டிலேயே சுலபமாக செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி என்று பார்க்கலாம்.",
            "tags": ["chettinad chicken biryani", "chicken biryani recipe in tamil"],
        }, BIRYANI, "tamil")
        codes = [issue["code"] for issue in gate["issues"]]
        self.assertNotIn("unrelated_tag", codes)
        self.assertNotIn("non_contextual_tags", codes)

    def test_explaining_why_allows_causal_language(self):
        gate = _gate({
            "title": "How to Make Cold Brew Coffee at Home",
            "description": COLD_BREW_DESC + " The long, cold steep results in a smoother cup.",
        }, COLD_BREW)
        self.assertNotIn("invented_causality", [issue["code"] for issue in gate["issues"]])


class GateStillRejectsBadCopyTests(unittest.TestCase):
    """Loosening the false positives must not let genuinely bad output through."""

    def test_word_salad_title_is_rejected_and_capped(self):
        gate = _gate({"title": "How to you how make cold brew coffee home without", "description": COLD_BREW_DESC}, COLD_BREW)
        self.assertFalse(gate["passed"])
        self.assertLessEqual(gate["final_seo_quality"]["title_score"], 35.0)

    def test_clinical_claims_are_banned_everywhere(self):
        gate = _gate({"title": "How to Make Cold Brew Coffee at Home", "description": COLD_BREW_DESC + " It helps with anxiety."}, COLD_BREW)
        self.assertIn("unsupported_context", [issue["code"] for issue in gate["issues"]])
        self.assertIn("anxiety", next(i["message"] for i in gate["issues"] if i["code"] == "unsupported_context"))

    def test_keyword_stuffing_is_still_a_tag_list(self):
        gate = _gate({"title": "How to Make Cold Brew Coffee at Home",
                      "description": "cold brew, cold brew coffee, cold brew recipe, cold brew at home, best cold brew, cold brew ratio"}, COLD_BREW)
        self.assertIn("tag_list_contamination", [issue["code"] for issue in gate["issues"]])

    def test_unrelated_english_tags_on_a_tamil_script_are_rejected(self):
        gate = _gate({"title": "செட்டிநாடு சிக்கன் பிரியாணி", "description": "செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி.",
                      "tags": ["easy mutton curry"]}, BIRYANI, "tamil")
        self.assertIn("unrelated_tag", [issue["code"] for issue in gate["issues"]])

    def test_reflective_quotes_still_cannot_invent_context(self):
        gate = _gate(
            {"title": "When he never told you the truth #shorts",
             "description": f"“{QUOTE}”\n\nA late night thought about a boyfriend who lied."},
            QUOTE, brief={"exact_quote": QUOTE, "video_format": "Short"},
        )
        self.assertIn("unsupported_context", [issue["code"] for issue in gate["issues"]])

    def test_quotes_still_cannot_invent_causality(self):
        gate = _gate(
            {"title": "The quiet cost of hidden truths #shorts",
             "description": f"“{QUOTE}”\n\nSecrets like this lead to lasting distrust."},
            QUOTE, brief={"exact_quote": QUOTE, "video_format": "Short"},
        )
        self.assertIn("invented_causality", [issue["code"] for issue in gate["issues"]])


class TitleFluencyTests(unittest.TestCase):
    def test_known_broken_titles_are_caught(self):
        for title in ("How to you how make cold brew coffee home without",
                      "How to honest review samsung galaxy s25 ultra after days",
                      "Cold brew coffee at home without"):
            with self.subTest(title=title):
                self.assertTrue(title_fluency_issues(title))

    def test_natural_titles_pass(self):
        for title in ("How to Make Cold Brew Coffee at Home",
                      "Samsung Galaxy S25 Ultra Review After 30 Days",
                      "Step by Step Guide to Sourdough",
                      "The realization that they never would have told you 🥀 #shorts",
                      "FastAPI use panni oru simple REST API build panradhu epdi"):
            with self.subTest(title=title):
                self.assertEqual(title_fluency_issues(title), [])

    def test_keyword_placement(self):
        self.assertEqual(keyword_placement("Cold Brew Coffee at Home in 5 Minutes", "cold brew coffee"), "front")
        self.assertEqual(keyword_placement("My Morning Routine", "cold brew coffee"), "missing")
        self.assertEqual(
            keyword_placement("செட்டிநாடு சிக்கன் பிரியாணி | Easy Recipe", "chettinad chicken biryani"), "front",
        )


class TagSelectionTests(unittest.TestCase):
    def test_model_numbers_in_the_source_are_valid_tags(self):
        content = {"samsung", "galaxy", "s25", "ultra", "review", "s24"}
        for tag in ("galaxy s25 ultra review", "s25 ultra"):
            with self.subTest(tag=tag):
                self.assertIsNone(_classify(tag, "", content, set())[1])

    def test_a_number_the_creator_never_wrote_is_rejected(self):
        self.assertEqual(_classify("best phones 2023", "", {"best", "phones"}, set())[1], "number_not_in_source")

    def test_tamil_video_keeps_english_search_tags(self):
        brief = build_creator_brief(script=BIRYANI, language="tamil", video_format="tutorial")
        tags, _ = select_final_tags(
            {"candidates": [], "content_terms": []},
            generated_tags=["chettinad chicken biryani", "chicken biryani recipe in tamil", "easy mutton curry"],
            title="செட்டிநாடு சிக்கன் பிரியாணி", script=BIRYANI, creator_brief=brief,
        )
        self.assertIn("chettinad chicken biryani", tags)
        self.assertIn("chicken biryani recipe in tamil", tags)
        self.assertNotIn("easy mutton curry", tags)

    def test_demand_validated_variants_of_one_keyword_are_all_kept(self):
        items = [
            {"keyword": phrase, "keyword_relevance_score": score, "classification": "long_tail",
             "evidence_count": 0, "demand_validated": True}
            for phrase, score in (("cold brew coffee", 90), ("cold brew coffee recipe", 88),
                                  ("how to make cold brew coffee at home", 86))
        ]
        self.assertEqual(len(_diverse_tag_selection(items, limit=12)), 3)


class SearchDemandTests(unittest.TestCase):
    DEMAND = {"suggestions": {
        "chettinad chicken biryani": [
            "chettinad chicken biryani", "chettinad chicken biryani in tamil",
            "chettinad chicken biryani recipe in tamil", "chettinad chicken biryani in malayalam",
        ],
    }}

    def test_rank_and_head_term_matching(self):
        index = suggestion_index(self.DEMAND)
        self.assertEqual(demand_rank("chettinad chicken biryani in tamil", index), 1)
        self.assertEqual(demand_rank("Chettinad Chicken Biryani", index), 0)
        self.assertIsNone(demand_rank("mutton curry", index))

    def test_only_suggestions_true_of_the_video_become_candidates(self):
        source = {"செட்டிநாடு", "சிக்கன்", "பிரியாணி", "tamil"}
        content = {"செட்டிநாடு", "சிக்கன்", "பிரியாணி"}
        self.assertTrue(_suggestion_is_grounded("chettinad chicken biryani recipe in tamil", source, content))
        self.assertFalse(_suggestion_is_grounded("chettinad chicken biryani in malayalam", source, content))

    @patch("win_engine.ingestion.search_suggest.httpx.get", side_effect=httpx.ConnectError("offline"))
    def test_lookup_fails_soft(self, _get):
        result = SearchSuggestClient(enabled=True, timeout_seconds=1, max_queries=3).fetch(["cold brew coffee"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["suggestions"], {})

    @patch("win_engine.ingestion.search_suggest.httpx.get")
    def test_lookup_parses_and_caps_queries(self, get):
        get.return_value = MagicMock(status_code=200, content=b'["cold brew",["cold brew","cold brew recipe"]]')
        result = SearchSuggestClient(enabled=True, timeout_seconds=1, max_queries=2).fetch(["a", "b", "c"])
        self.assertEqual(get.call_count, 2)
        self.assertEqual(result["suggestions"]["a"], ["cold brew", "cold brew recipe"])

    def test_disabled_client_makes_no_requests(self):
        with patch("win_engine.ingestion.search_suggest.httpx.get") as get:
            result = SearchSuggestClient(enabled=False, timeout_seconds=1, max_queries=6).fetch(["cold brew"])
        get.assert_not_called()
        self.assertEqual(result["status"], "disabled")


class FallbackTests(unittest.TestCase):
    def test_instructional_fallback_title_is_a_readable_source_phrase(self):
        brief = build_creator_brief(script=COLD_BREW, video_format="tutorial")
        package = _content_specific_fallback(creator_topic(brief), [], brief)
        self.assertEqual(package["title"], "How to make cold brew coffee at home")
        self.assertEqual(title_fluency_issues(package["title"]), [])

    def test_review_fallback_names_the_product(self):
        brief = build_creator_brief(script=SAMSUNG, video_format="review")
        package = _content_specific_fallback(creator_topic(brief), [], brief)
        self.assertEqual(package["title"], "Samsung Galaxy S25 Ultra Review After 30 Days")
        self.assertGreaterEqual(len(package["variants"]), 2)

    def test_fallback_description_never_cuts_a_sentence(self):
        brief = build_creator_brief(script=COLD_BREW, video_format="tutorial")
        description = _content_specific_fallback(creator_topic(brief), [], brief)["description"]
        self.assertNotIn("…", description)
        self.assertTrue(description.rstrip().endswith("."))

    def test_trimming_drops_whole_trailing_phrases(self):
        self.assertEqual(
            _trim_title_span("how to make cold brew coffee at home without any special equipment"),
            "How to make cold brew coffee at home",
        )


class HashtagTests(unittest.TestCase):
    def test_top_up_comes_from_subject_tags_not_category_presets(self):
        hashtags = force_hashtags([], "", "education", tags=["cold brew coffee", "mason jar"])
        self.assertEqual(hashtags, ["#ColdBrewCoffee", "#MasonJar"])
        self.assertNotIn("#StudyTips", force_hashtags([], "", "education"))

    def test_placeholder_topics_never_become_hashtags(self):
        self.assertNotIn("#DeepQuote", force_hashtags([], "deep quote", "quotes"))

    def test_tamil_hashtags_are_not_duplicated(self):
        description = format_upload_ready_description("சுவையான பிரியாணி.\n\n#பிரியாணி", ["#பிரியாணி"])
        self.assertEqual(description.count("#பிரியாணி"), 1)


class FalsePositiveGuardTests(unittest.TestCase):
    """The new checks must not reject legitimate copy."""

    def test_idiomatic_repetition_is_not_garbled(self):
        for title in ("The Good, the Bad and the Ugly", "A Day in a Life of a Chef",
                      "How to Cook Rice and How to Store It", "Reunited After Years",
                      "Bigger and Bigger Waves", "Step by Step Mango Ice Cream"):
            with self.subTest(title=title):
                self.assertEqual(title_fluency_issues(title), [])

    def test_two_search_phrases_stuck_together_are_flagged(self):
        codes = [i["code"] for i in title_fluency_issues("2 ingredient ice cream instant mango ice cream #shorts")]
        self.assertIn("keyword_stuffed_title", codes)

    def test_repeated_units_in_an_ingredient_list_are_not_a_tag_dump(self):
        from win_engine.analysis.generation_quality import _looks_like_tag_list

        self.assertFalse(_looks_like_tag_list("1 cup rice, 1 cup dal, 1 cup urad dal, 1 cup sugar, 1 cup milk, 1 cup water"))


class ReviewRoundTests(unittest.TestCase):
    """Defects found by the first live re-run and fixed before the final one."""

    def test_garbled_suggestions_and_verb_led_entities_are_not_tags(self):
        from win_engine.analysis.keyword_research import _repeats_a_word

        self.assertTrue(_repeats_a_word("chettinad biryani chicken biryani"))
        self.assertFalse(_repeats_a_word("step by step biryani"))
        self.assertEqual(_classify("make chettinad chicken", "entity", {"chettinad", "chicken"}, set())[1], "malformed_entity")
        self.assertIsNone(_classify("samsung galaxy s25", "entity", {"samsung", "galaxy", "s25"}, set())[1])

    def test_a_script_that_names_no_subject_is_flagged(self):
        from win_engine.analysis.generation_quality import _source_is_topicless

        vague = ("Today I want to talk about the thing that everyone gets wrong about it, and honestly "
                 "why it matters way more than you think. Stay till the end.")
        self.assertTrue(_source_is_topicless(vague, {}))
        self.assertFalse(_source_is_topicless(QUOTE, {}))
        self.assertFalse(_source_is_topicless(BIRYANI, {}))

    def test_a_format_the_creator_never_declared_is_rejected(self):
        script = "My three favourite ways to store fresh herbs so they last two weeks in the fridge."
        package = {"title": "How to Store Fresh Herbs So They Last Two Weeks",
                   "description": "In this vlog I show three ways to store fresh herbs so they last two weeks."}
        self.assertIn("invented_format", [i["code"] for i in _gate(package, script)["issues"]])
        declared = _gate(package, script, brief={"video_format": "vlog"})
        self.assertNotIn("invented_format", [i["code"] for i in declared["issues"]])

    def test_demand_only_counts_when_it_names_the_subject(self):
        from win_engine.analysis.keyword_research import _validated_demand_rank

        index = suggestion_index({"suggestions": {"x": ["hidden details", "gta 6 trailer 2 analysis", "perspective"]}})
        subjects = {"gta", "vice"}
        self.assertIsNone(_validated_demand_rank("hidden details", index, subjects))
        self.assertIsNone(_validated_demand_rank("perspective", index, subjects))
        self.assertEqual(_validated_demand_rank("gta 6 trailer 2 analysis", index, subjects), 1)

    def test_demand_seeds_name_the_subject(self):
        from win_engine.analysis.keyword_research import demand_seed_phrases

        research = {"subject_terms": ["fastapi", "api", "python"],
                    "candidates": [{"keyword": "hidden details", "classification": "long_tail"},
                                   {"keyword": "python api build", "classification": "long_tail"}]}
        seeds = demand_seed_phrases(research, {"primary_topic": "FastAPI REST API"},
                                    {"video_format": "tutorial", "content": "FastAPI tutorial"})
        self.assertIn("fastapi tutorial", seeds)
        self.assertNotIn("hidden details", seeds)

    def test_cooking_tutorials_seed_with_recipe(self):
        from win_engine.analysis.keyword_research import demand_seed_phrases

        seeds = demand_seed_phrases(
            {"subject_terms": ["chettinad", "chicken", "biryani"], "candidates": []},
            {"primary_topic": "chettinad chicken biryani"},
            {"video_format": "tutorial", "content": "chettinad chicken biryani recipe at home"},
        )
        self.assertIn("chettinad chicken biryani recipe", seeds)

    def test_main_search_phrase_names_the_subject(self):
        from win_engine.analysis.generation_quality import primary_search_phrase

        evidence = {"subject_terms": ["chatgpt", "excel", "vlookup"], "selected_keywords": [
            {"keyword": "if function", "demand_validated": True},
            {"keyword": "chatgpt for excel", "demand_validated": True},
        ]}
        self.assertEqual(primary_search_phrase(evidence), "chatgpt for excel")

    def test_near_duplicate_hashtags_are_not_repeated(self):
        from win_engine.analysis.generation_quality import focused_short_hashtags

        hashtags = focused_short_hashtags(["2 ingredient ice cream", "2 ingredient ice cream recipe", "instant mango ice cream"])
        self.assertEqual(hashtags, ["#shorts", "#2IngredientIceCream", "#MangoIceCream"])
        self.assertEqual(force_hashtags(["#ColdBrew", "#ColdBrewCoffee", "#Coffee"], "", "cooking"), ["#ColdBrew", "#Coffee"])

    def test_searched_emotional_phrases_survive(self):
        brief = {"exact_quote": QUOTE, "video_format": "Short"}
        research = {"candidates": [], "content_terms": [],
                    "search_demand": {"suggestions": {"betrayal quotes": ["betrayal quotes", "betrayal quotes in relationship"]}}}
        tags, _ = select_final_tags(research, generated_tags=["betrayal quotes"], title="x",
                                    script=QUOTE, creator_brief=brief, is_short=True)
        self.assertIn("betrayal quotes", tags)


class LiveAuditRoundTwoTests(unittest.TestCase):
    """Defects found by the second live run over the original and holdout scripts."""

    def test_spaced_hashtag_is_joined_not_split(self):
        from win_engine.analysis.topic_lock import normalize_hashtag

        self.assertEqual(normalize_hashtag("#cold brew"), "#ColdBrew")
        self.assertEqual(normalize_hashtag("coffee"), "#coffee")
        self.assertEqual(normalize_hashtag("#VLOOKUP"), "#VLOOKUP")
        self.assertEqual(normalize_hashtag("#செட்டிநாடு பிரியாணி"), "#செட்டிநாடுபிரியாணி")
        self.assertEqual(normalize_hashtag(" # "), "")
        self.assertEqual(force_hashtags(["#cold brew", "coffee", "#home cafe"], "", "cooking"),
                         ["#ColdBrew", "#coffee", "#HomeCafe"])

    def test_description_hashtag_line_is_not_repeated(self):
        # The description is formatted twice; "#cold brew" used to survive the
        # first pass as prose and be appended again on the second.
        once = format_upload_ready_description("Cold brew at home.", ["#cold brew", "#coffee"],
                                               category="cooking", topic="cold brew")
        twice = format_upload_ready_description(once, ["#cold brew", "#coffee"],
                                                category="cooking", topic="cold brew")
        self.assertEqual(twice.count("#ColdBrew"), 1)
        self.assertNotIn("#cold ", twice)

    def test_names_keep_the_creators_casing(self):
        from win_engine.analysis.topic_lock import restore_source_casing, source_casing_map

        casing = source_casing_map(SAMSUNG)
        self.assertEqual(restore_source_casing("Samsung galaxy s25 ultra review: 30 days later", casing),
                         "Samsung Galaxy S25 Ultra review: 30 days later")
        # Ordinary words the source writes in lowercase are left alone.
        self.assertEqual(restore_source_casing("an honest review of battery life", casing),
                         "an honest review of battery life")

    def test_casing_ignores_contractions_and_title_case_headings(self):
        from win_engine.analysis.topic_lock import restore_source_casing, source_casing_map

        casing = source_casing_map("I met Don at the cafe. We don't talk much.")
        self.assertEqual(restore_source_casing("we don't know", casing), "we don't know")
        casing = source_casing_map("My Honest Review After Thirty Days\nThe phone is honest about battery.")
        self.assertEqual(restore_source_casing("my honest review after thirty days", casing),
                         "my honest review after thirty days")

    def test_casing_in_mixed_script_and_for_code_names(self):
        from win_engine.analysis.topic_lock import restore_source_casing, source_casing_map

        tamil_tech = ("இந்த வீடியோவில் ChatGPT பயன்படுத்தி Excel-ல் formula எழுதுவது எப்படி என்று பார்க்கலாம். "
                      "VLOOKUP, SUMIF மற்றும் IF formula-க்களை ஒவ்வொன்றாக விளக்குகிறேன்.")
        casing = source_casing_map(tamil_tech)
        self.assertEqual(restore_source_casing("chatgpt excel vlookup tutorial", casing),
                         "ChatGPT Excel VLOOKUP tutorial")
        # Code names that are also ordinary words are never lifted.
        casing = source_casing_map("Create a GET endpoint and a POST endpoint, then use the IF formula.")
        self.assertEqual(restore_source_casing("If you get stuck, post a comment and see if it helps.", casing),
                         "If you get stuck, post a comment and see if it helps.")
        self.assertEqual(force_hashtags(["#chatgpt"], "", "tech", casing={"chatgpt": "ChatGPT"}), ["#ChatGPT"])

    def test_quote_subject_is_its_theme_not_a_pronoun(self):
        from win_engine.analysis.keyword_research import (
            _source_terms, demand_seed_phrases, quote_themes, subject_terms,
        )

        semantic = {"primary_topic": "hidden deceit", "entities": ["you"]}
        terms = subject_terms(semantic, [], _source_terms(QUOTE, {}), themes=quote_themes(QUOTE))
        self.assertIn("betrayal", terms)
        self.assertNotIn("you", terms)
        seeds = demand_seed_phrases({"subject_terms": sorted(terms), "candidates": []}, semantic,
                                    {"exact_quote": QUOTE, "video_format": "Short"})
        self.assertEqual(seeds[0], "betrayal quotes")

    def test_partial_entity_from_competitor_titles_is_rejected(self):
        from win_engine.analysis.keyword_research import build_keyword_research

        script = ("My 20 minute home workout for beginners with no equipment. We do squats, push-ups "
                  "and lunges, three rounds with 30 seconds of rest.")
        brief = {"video_format": "tutorial", "language": "english"}
        research = build_keyword_research(
            script=script, semantic={"primary_topic": "beginner home workout"}, youtube_results=[],
            research_queries=[], entity_signals=[{"entity": "No Repeat Home"}], creator_brief=brief,
        )
        tags, evidence = select_final_tags(research, generated_tags=[], title="Beginner home workout",
                                           script=script, creator_brief=brief)
        self.assertNotIn("no repeat home", tags)
        self.assertIn("entity_not_in_source", {item["reason"] for item in evidence["rejected_candidates"]
                                               if item["keyword"] == "no repeat home"})

    def test_one_modifier_cannot_crowd_the_tag_field(self):
        keywords = [
            "samsung s25 ultra price", "s25 ultra price in india", "samsung galaxy s25 ultra price",
            "samsung s25 ultra price in india", "s25 ultra best price in india", "samsung s25 ultra review",
            "galaxy s25 ultra camera",
        ]
        items = [
            {"keyword": keyword, "classification": "long_tail", "demand_validated": True,
             "keyword_relevance_score": 95, "evidence_count": 3}
            for keyword in keywords
        ]
        chosen = [item["keyword"] for item in _diverse_tag_selection(
            items, limit=12, subjects={"samsung", "galaxy", "s25", "ultra"})]
        self.assertLessEqual(sum("price" in keyword for keyword in chosen), 2)
        self.assertIn("samsung s25 ultra review", chosen)
        self.assertIn("galaxy s25 ultra camera", chosen)

    def test_title_with_the_real_search_phrase_wins_a_tie(self):
        from win_engine.generation.quality_refinement import title_demand_words

        evidence = {"search_demand": {"grounded_suggestions": ["making cold brew coffee at home", "cold brew coffee"],
                                      "validated_keywords": []}}
        self.assertEqual(title_demand_words("Making cold brew coffee at home without special gear", evidence), 6)
        self.assertEqual(title_demand_words("Step-by-step cold brew coffee with a paper filter", evidence), 3)
        self.assertEqual(title_demand_words("Iced coffee basics", evidence), 0)

    def test_today_is_not_a_vlog_cue(self):
        brief = build_creator_brief(script="Today I want to talk about the thing everyone gets wrong about it.")
        self.assertEqual(brief["video_format"], "talking_head")

    def test_guessed_format_is_not_treated_as_declared(self):
        script = "Let me tell you about my life as a night-shift nurse in Chennai and what it taught me."
        description = "In this vlog I share my life as a night-shift nurse in Chennai and what it taught me."
        guessed = build_creator_brief(script=script)
        self.assertEqual(guessed["video_format"], "vlog")
        codes = {item["code"] for item in _gate({"title": "My life as a night-shift nurse in Chennai",
                                                  "description": description}, script, brief=guessed)["issues"]}
        self.assertIn("invented_format", codes)
        declared = build_creator_brief(script=script, video_format="vlog")
        codes = {item["code"] for item in _gate({"title": "My life as a night-shift nurse in Chennai",
                                                  "description": description}, script, brief=declared)["issues"]}
        self.assertNotIn("invented_format", codes)

    def test_short_hashtags_drop_search_intent_but_keep_meaning(self):
        from win_engine.analysis.generation_quality import focused_short_hashtags

        self.assertEqual(
            focused_short_hashtags(["easy mango ice cream recipe", "how to make mango ice cream", "ice cream", "yt", "shorts"]),
            ["#shorts", "#MangoIceCreamRecipe", "#IceCream"],
        )
        self.assertEqual(focused_short_hashtags(["chettinad biryani recipe in tamil"]),
                         ["#shorts", "#ChettinadBiryaniRecipe"])
        self.assertEqual(focused_short_hashtags(["gta 6 trailer"], {"gta": "GTA"}), ["#shorts", "#GTA6Trailer"])

    def test_title_timescale_must_come_from_the_source(self):
        from win_engine.analysis.generation_quality import title_duration_issues

        codes = lambda title, source: [item["code"] for item in title_duration_issues(title, source)]  # noqa: E731
        self.assertEqual(codes("Honest review of cold brew coffee after days", COLD_BREW), ["invented_timescale"])
        self.assertEqual(codes("Samsung Galaxy S25 Ultra review after days", SAMSUNG), ["dropped_number"])
        self.assertEqual(codes("Samsung Galaxy S25 Ultra review after 30 days", SAMSUNG), [])
        self.assertEqual(codes("Cold brew coffee in 12 hours", COLD_BREW), [])
        self.assertEqual(codes("The best phone of the year", SAMSUNG), [])
        self.assertEqual(codes("Chettinad biryani in 30 minutes", BIRYANI), [])  # Tamil units are not readable here
        gate = _gate({"title": "Honest review of cold brew coffee after days", "description": COLD_BREW_DESC}, COLD_BREW)
        self.assertFalse(gate["passed"])

    def test_adjective_head_is_not_seeded_alone(self):
        from win_engine.analysis.keyword_research import demand_seed_phrases

        seeds = demand_seed_phrases(
            {"subject_terms": ["cold", "brew", "coffee"], "candidates": []},
            {"primary_topic": "cold brew coffee"},
            {"video_format": "tutorial", "content": COLD_BREW},
        )
        self.assertIn("cold brew coffee recipe", seeds)
        self.assertNotIn("cold recipe", seeds)

    def test_html_entities_never_reach_the_package(self):
        from win_engine.ingestion.youtube_client import unescape_result
        from win_engine.llm.seo_writer import _validate

        row = unescape_result({"title": "GTA 6 Hidden Details &amp; Easter Eggs", "channel_title": "Rock&#39;s"})
        self.assertEqual(row["title"], "GTA 6 Hidden Details & Easter Eggs")
        self.assertEqual(row["channel_title"], "Rock's")
        package = _validate({"title": "GTA 6 Trailer 2 Breakdown: Vice City &amp; Graphics",
                             "variants": ["Vice City &amp; GTA 5"], "description": "Details &amp; more.",
                             "tags": ["gta 6"], "hashtags": ["#GTA6"]})
        self.assertEqual(package["title"], "GTA 6 Trailer 2 Breakdown: Vice City & Graphics")
        self.assertNotIn("&amp;", package["description"] + " ".join(package["variants"]))

    def test_hashtags_from_tags_keep_name_casing(self):
        self.assertEqual(force_hashtags([], "", "gaming", tags=["gta 5 comparison"], casing={"gta": "GTA"}),
                         ["#GTA5Comparison"])


class FinalRunPrecisionTests(unittest.TestCase):
    """Precision defects found by the last live run."""

    def test_a_previous_model_gets_at_most_one_tag(self):
        keywords = [
            "samsung galaxy s25 ultra review", "s24 ultra", "s24 ultra samsung", "samsung galaxy s24",
            "samsung galaxy s24 ultra", "s25 ultra vs s24 ultra", "samsung galaxy s25 ultra price",
        ]
        items = [
            {"keyword": keyword, "classification": "long_tail", "demand_validated": True,
             "keyword_relevance_score": 95, "evidence_count": 3}
            for keyword in keywords
        ]
        chosen = [item["keyword"] for item in _diverse_tag_selection(
            items, limit=12, subjects={"samsung", "galaxy", "s25", "s24", "ultra"}, primary_codes={"s25"})]
        self.assertEqual(sum("s24" in keyword and "s25" not in keyword for keyword in chosen), 1)
        self.assertIn("s25 ultra vs s24 ultra", chosen)  # names the video's own model too

    def test_quote_theme_in_title_counts_as_the_search_phrase(self):
        self.assertEqual(keyword_placement("Secret betrayal hurts differently #shorts", "betrayal quotes"), "front")
        self.assertEqual(keyword_placement("When they never would have told you #shorts", "betrayal quotes"), "missing")

    def test_one_letter_model_names_must_match_the_source(self):
        from win_engine.analysis.keyword_research import _foreign_single_letters, _single_letters

        letters = _single_letters("What the PS5 and Xbox Series X footage and the game's GTA 5 map tell us.")
        self.assertEqual(_foreign_single_letters("xbox series s", letters), {"s"})
        self.assertEqual(_foreign_single_letters("xbox series x graphics", letters), set())
        self.assertEqual(_foreign_single_letters("vice city map in gta 5", letters), set())
        self.assertEqual(_foreign_single_letters("how to make a map", letters), set())

    def test_phrase_youtube_has_no_searches_for_is_skipped(self):
        validated = [
            {"keyword": keyword, "classification": "long_tail", "demand_validated": True,
             "keyword_relevance_score": 95, "evidence_count": 3}
            for keyword in ("excel tutorial", "chatgpt excel", "vlookup tutorial")
        ]
        unvalidated = [
            {"keyword": keyword, "classification": "long_tail", "keyword_relevance_score": 90, "evidence_count": 0}
            for keyword in ("vlookup sumif if formula chatgpt", "sumif formula examples")
        ]
        chosen = [item["keyword"] for item in _diverse_tag_selection(
            validated + unvalidated, limit=12, subjects={"excel", "chatgpt", "vlookup", "sumif"},
            unsearched={"vlookup sumif if formula chatgpt"})]
        self.assertNotIn("vlookup sumif if formula chatgpt", chosen)
        self.assertIn("sumif formula examples", chosen)

    def test_title_led_by_another_real_search_is_not_missing_its_keyword(self):
        script = ("I compare investing Rs 5,000 every month through an SIP with putting Rs 60,000 in at once, "
                  "using the last 10 years of Nifty 50 index fund returns, and explain the risk of timing the market.")
        evidence = {
            "subject_terms": ["sip", "lump", "sum", "nifty", "index", "fund", "returns"],
            "selected_keywords": [
                {"keyword": keyword, "demand_validated": True, "keyword_relevance_score": 95,
                 "source_support_score": 100, "classification": "long_tail"}
                for keyword in ("nifty 50 index fund returns", "sip vs lump sum")
            ],
        }
        gate = evaluate_package_quality(
            {"title": "SIP vs lump sum: Rs 60,000 Nifty 50 test for beginners", "variants": [],
             "description": "SIP vs lump sum compared using the last 10 years of Nifty 50 index fund returns.",
             "tags": ["nifty 50 index fund returns", "sip vs lump sum"], "hashtags": []},
            script=script, creator_brief={}, require_shorts_tags=False, tag_evidence=evidence,
            enforce_final_tag_rules=False,
        )
        codes = {item["code"] for item in gate["final_seo_quality"]["warnings"]}
        self.assertNotIn("primary_keyword_missing_from_title", codes)

    def test_travel_vlog_is_not_read_as_finance(self):
        munnar = ("A day in Munnar: we hiked to Top Station at sunrise, visited a tea factory to see how tea is "
                  "processed, and ended with a boat ride on Mattupetty Dam. At the end I share the full budget "
                  "for two people, including the homestay and the jeep hire.")
        self.assertEqual(infer_category(munnar), "vlog")
        # One cooking word against one finance word is ambiguous, not finance.
        self.assertEqual(infer_category("tea and a budget"), "general")

    def test_production_jargon_is_not_viewer_copy(self):
        script = "Today I want to talk about the thing that everyone gets wrong about budgeting."
        brief = build_creator_brief(script=script)
        gate = _gate({"title": "What everyone gets wrong about budgeting",
                      "description": "In this talking head video we break down what everyone gets wrong about budgeting."},
                     script, brief=brief)
        self.assertIn("production_jargon", {item["code"] for item in gate["issues"]})

    def test_guessed_format_is_not_given_to_the_writer_as_fact(self):
        from win_engine.llm.seo_writer import _build_creator_brief_block

        script = "Today I want to talk about the thing that everyone gets wrong about budgeting."
        self.assertNotIn("Video format", _build_creator_brief_block(build_creator_brief(script=script)))
        self.assertIn("Video format: vlog",
                      _build_creator_brief_block(build_creator_brief(script=script, video_format="vlog")))


class YouTubeRateLimitTests(unittest.TestCase):
    """A burst limit dropped research evidence in 26 of one audit run's requests."""

    @staticmethod
    def _response(status, payload):
        import requests

        response = MagicMock(status_code=status)
        response.json.return_value = payload
        if status >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(response=response)
        return response

    def test_burst_rate_limit_is_retried(self):
        from win_engine.ingestion.youtube_client import YouTubeClient

        limited = self._response(403, {"error": {"errors": [{"reason": "rateLimitExceeded"}]}})
        ok = self._response(200, {"items": []})
        with patch("win_engine.ingestion.youtube_client.requests.get", side_effect=[limited, ok]) as get, \
                patch("win_engine.ingestion.youtube_client.time.sleep") as sleep:
            self.assertEqual(YouTubeClient(["key"], timeout_seconds=5)._request_json("u", {}), {"items": []})
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once()

    def test_daily_quota_is_not_retried(self):
        from win_engine.ingestion.youtube_client import YouTubeClient

        exhausted = self._response(403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})
        with patch("win_engine.ingestion.youtube_client.requests.get", side_effect=[exhausted]) as get, \
                patch("win_engine.ingestion.youtube_client.time.sleep") as sleep:
            self.assertEqual(YouTubeClient(["key"], timeout_seconds=5)._request_json("u", {}), {})
        self.assertEqual(get.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
