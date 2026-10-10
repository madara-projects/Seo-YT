"""AI Shorts SEO: the quote's reading decides the tags, hashtags and title emoji; the Creator page is untouched.

Everything is offline: search suggestions come from a fake client, Gemini is
off, and the Flow planner is mocked.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from win_engine.analysis.generation_quality import title_body, title_emojis
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation import ai_shorts, ai_shorts_seo as seo
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.llm import gemini_client

HEART = "The best way to not get your heart broken is to pretend that you don't have one."
HEALED = "My heart finally healed, and I didn't even notice when."
PROUD = "Be proud of how hard you are trying."
USEFUL = "Some people only love you when you are useful to them."
DISCIPLINE = "Discipline is doing it even when you don't feel like it."
EXPLAIN = "Stop explaining yourself to people who already decided to misunderstand you."


class FakeSuggest:
    """YouTube search suggestions: every query is typed except those in ``untyped``."""

    def __init__(self, untyped: tuple[str, ...] = (), *, status: str = "ok") -> None:
        self.untyped = untyped
        self.status = status
        self.asked: list[str] = []

    def fetch(self, queries, *, language="english", region="global"):
        queries = list(queries)[:6]
        self.asked.extend(queries)
        if self.status != "ok":
            return {"status": self.status, "queries": [], "suggestions": {}, "failed_queries": []}
        suggestions = {query: ([] if any(word in query for word in self.untyped) else [query, f"{query} for him"])
                       for query in queries}
        return {"status": "ok", "queries": queries, "suggestions": suggestions, "failed_queries": []}


class Broken:
    def fetch(self, *args, **kwargs):
        raise RuntimeError("no network")


def _brief(quote: str, client=None, plan=None) -> dict:
    reading = seo.quote_understanding(quote, plan or {})
    verified = seo.verify_subject_tags(reading, quote=quote, client=client or FakeSuggest())
    return {"exact_quote": quote, "ai_shorts": {**reading, **verified}}


class ReadingTests(unittest.TestCase):
    def test_the_local_reading_is_negation_and_sentiment_aware(self):
        self.assertEqual(seo.local_tone(HEART), "numb")  # not "heartbroken": the heart is not broken
        self.assertEqual(seo.local_tone(HEALED), "healing")
        self.assertEqual(seo.local_tone(PROUD), "hopeful")  # gentle encouragement, not the resolve of discipline
        self.assertEqual(seo.local_tone(DISCIPLINE), "empowering")  # "don't feel like it" is not numbness
        self.assertEqual(seo.local_tone(USEFUL), "sad")
        self.assertNotEqual(seo.local_tone("Don't cry because it's over, smile because it happened."), "sad")
        self.assertEqual(seo.local_tone("The quietest people usually have the loudest minds."), "")

    def test_the_planners_reading_leads_and_bad_values_are_dropped(self):
        plan = {"creative_direction": {
            "quote_meaning": "Hiding feelings\nto stay safe.", "emotion": "guarded numbness", "tone": "numb",
            "search_themes": ["Heartbreak Quotes", "emotional numbness", "sad", "viral shorts quotes",
                              "a very long phrase that is far too long", 7],
        }}
        reading = seo.quote_understanding(HEART, plan)
        self.assertEqual((reading["tone"], reading["tone_source"]), ("numb", "planner"))
        self.assertEqual(reading["meaning"], "Hiding feelings to stay safe.")
        self.assertEqual(reading["planner_themes"], ["heartbreak quotes", "emotional numbness"])
        self.assertEqual(reading["search_themes"][:2], ["heartbreak quotes", "emotional numbness"])
        # A tone outside the contract, or a plan saved before the reading existed: read locally.
        for direction in ({"tone": "melancholy"}, None):
            with self.subTest(direction=direction):
                local = seo.quote_understanding(HEALED, {"creative_direction": direction} if direction else {})
                self.assertEqual((local["tone"], local["tone_source"]), ("healing", "quote_words"))

    def test_the_planners_reading_survives_a_scene_it_threw_away(self):
        # A symbolic scene leaves no creative direction, but the reading still holds.
        plan = {"quote_understanding": {
            "quote_meaning": "Acting numb so nobody can hurt you again.", "emotion": "guarded numbness",
            "tone": "numb", "search_themes": ["heartbreak quotes", "emotional numbness", "cold heart quotes"],
        }}
        reading = seo.quote_understanding(HEART, plan)
        self.assertEqual((reading["tone"], reading["tone_source"]), ("numb", "planner"))
        self.assertEqual(reading["meaning"], "Acting numb so nobody can hurt you again.")
        self.assertEqual(reading["planner_themes"], ["heartbreak quotes", "emotional numbness", "cold heart quotes"])
        # When both are present, the kept creative direction's own values lead.
        both = seo.quote_understanding(HEART, {**plan, "creative_direction": {"tone": "heartbroken"}})
        self.assertEqual(both["tone"], "heartbroken")


TIRED = "I'm tired of trying to make people stay"
NOT_PROUD = "I'm not proud of who I became"
SARCASTIC = "Oh sure, I'm so proud of how well I'm doing."


class ToneFitTests(unittest.TestCase):
    """A theme word never speaks over the quote's tone: "trying" in a weary quote is not motivation."""

    def assert_not_motivational(self, quote: str, reading: dict) -> None:
        brief = {"exact_quote": quote, "ai_shorts": reading}
        self.assertNotIn("#motivation", seo.ai_short_hashtags(brief, quote))
        self.assertFalse({"keep going quotes", "proud of yourself quotes", "motivational quotes"}
                         & set(reading["search_themes"]), reading["search_themes"])
        self.assertNotIn("💪", seo.style_title("A title", quote, brief))

    def test_a_weary_quote_with_the_word_trying_is_not_motivation(self):
        planned = seo.quote_understanding(TIRED, {"creative_direction": {"tone": "sad"}})
        self.assertEqual(planned["tone"], "sad")
        self.assert_not_motivational(TIRED, planned)
        self.assertEqual(seo.ai_short_hashtags({"ai_shorts": planned}, TIRED), ["#shorts", "#quotes", "#sadquotes"])
        local = seo.quote_understanding(TIRED, {})
        self.assertIn(local["tone"], {"sad", "lonely"})
        self.assert_not_motivational(TIRED, local)

    def test_a_negated_or_sarcastic_pride_is_not_motivation(self):
        local = seo.quote_understanding(NOT_PROUD, {})
        self.assertEqual(local["tone"], "sad")
        self.assert_not_motivational(NOT_PROUD, local)
        # Sarcasm is the planner's to read; its tone then decides over the word "proud".
        planned = seo.quote_understanding(SARCASTIC, {"creative_direction": {"tone": "bittersweet"}})
        self.assert_not_motivational(SARCASTIC, planned)
        self.assertEqual(seo.ai_short_hashtags({"ai_shorts": planned}, SARCASTIC)[-1], "#lifequotes")

    def test_a_theme_that_fits_the_tone_still_names_the_hashtag(self):
        planned = seo.quote_understanding(USEFUL, {"creative_direction": {"tone": "angry"}})
        self.assertEqual(seo.ai_short_hashtags({"ai_shorts": planned}, USEFUL)[-1], "#selfworth")
        planned = seo.quote_understanding(PROUD, {"creative_direction": {"tone": "uplifting"}})
        self.assertEqual(seo.ai_short_hashtags({"ai_shorts": planned}, PROUD)[-1], "#motivation")

    def test_three_planner_themes_lead_and_the_quotes_words_only_top_up(self):
        # Each planner theme is tied to the quote: by its tone family, or by the planner's reading ("effort").
        direction = {"tone": "empowering", "quote_meaning": "Your effort deserves your own recognition.",
                     "search_themes": ["inspirational quotes", "self worth quotes", "effort quotes"]}
        reading = seo.quote_understanding(PROUD, {"creative_direction": direction})
        verified = seo.verify_subject_tags(reading, quote=PROUD, client=FakeSuggest())
        names = [row["keyword"] for row in verified["subject_tags"]]
        self.assertEqual(names[:3], ["self worth quotes", "effort quotes", "inspirational quotes"])
        self.assertTrue(set(names[3:]) <= set(reading["search_themes"]) - set(direction["search_themes"]))


class DescriptionTests(unittest.TestCase):
    def test_a_description_left_with_the_quote_alone_gets_a_safe_question(self):
        brief = {"exact_quote": HEALED, "ai_shorts": seo.quote_understanding(HEALED, {})}
        bare = f"{HEALED}\n\n#shorts #quotes #healing"
        fixed = seo.with_reflection(bare, HEALED, brief)
        self.assertEqual(fixed, f"{HEALED}\n\nHave you noticed how far you have come?")
        self.assertEqual(seo.with_reflection(f"“{HEALED}”", HEALED, brief).splitlines()[-1],
                         "Have you noticed how far you have come?")
        # The writer's own line is kept whenever it survived.
        written = f"{HEALED}\n\nSome healing only shows when you look back.\n\n#shorts #quotes #healing"
        self.assertEqual(seo.with_reflection(written, HEALED, brief), written.rsplit("\n\n", 1)[0])

    def test_a_writer_line_the_sanitizer_drops_as_invented_leaves_a_safe_question(self):
        # The shared sanitizer drops a reflective line that invents context the
        # quote never states (a breakup here), which left a live healed-quote
        # package with the quote and its hashtags only.
        reply = json.dumps({
            "title": "My heart finally healed, and I didn't even notice when 🌿 #shorts",
            "variants": ["My heart finally healed, and I didn't even notice when 🌿 #shorts",
                         "When did your heart quietly heal? 🌱 #shorts",
                         "The day you realize the ache is gone from your heart 🌱 #shorts"],
            "description": f"{HEALED}\n\nHealing after a breakup takes time.",
            "tags": ["healing quotes"], "hashtags": ["#shorts", "#quotes", "#healing"],
        })
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(gemini_client, "is_available", return_value=True), \
                patch.object(gemini_client, "generate", return_value=reply), \
                patch.object(seo, "suggest_client", return_value=FakeSuggest()), \
                patch.object(ai_shorts, "_plan_flow_shots", return_value=_plan(HEALED)):
            package = ai_shorts.generate_ai_short(HistoryStore(str(Path(folder) / "d.db")), quote=HEALED, parts=1)["package"]
        self.assertEqual(package["generation_source"], "gemini")
        self.assertNotIn("breakup", package["description"])
        self.assertEqual(package["description"],
                         f"{HEALED}\n\nHave you noticed how far you have come?\n\n#shorts #quotes #healing")

    def test_every_safe_question_passes_the_quality_gate_for_its_quote(self):
        from win_engine.analysis.generation_quality import evaluate_package_quality

        for quote in (HEART, HEALED, PROUD, USEFUL, DISCIPLINE, TIRED, NOT_PROUD):
            with self.subTest(quote=quote):
                brief = {"exact_quote": quote, "on_screen_text": quote, "video_format": "youtube_shorts",
                         "content": quote, "ai_shorts": seo.quote_understanding(quote, {})}
                description = seo.with_reflection(quote, quote, brief)
                self.assertGreater(len(description.splitlines()), 1)
                gate = evaluate_package_quality(
                    {"title": f"{quote.rstrip('.')} #shorts", "variants": [], "description": description,
                     "tags": [], "hashtags": []},
                    script=quote, creator_brief=brief,
                )
                self.assertFalse([item for item in gate["issues"] if item.get("field") == "description"], gate["issues"])


class EmojiAndTitleTests(unittest.TestCase):
    def test_the_emoji_follows_the_tone_not_the_word_heart(self):
        self.assertEqual(seo.style_title("My heart finally healed 💔", HEALED), "My heart finally healed 🌱 #shorts")
        self.assertEqual(seo.style_title("Pretending you don't have a heart", HEART), "Pretending you don't have a heart 🖤 #shorts")
        # A written emoji that fits the tone stays; footage and literal objects do not.
        self.assertEqual(seo.style_title("Acting like it doesn't exist 🧊 #shorts", HEART), "Acting like it doesn't exist 🧊 #shorts")
        # The quote's theme leads its tone: self-respect is 👑, never a literal 🛑.
        self.assertEqual(seo.style_title("Stop explaining yourself to them 🛑", EXPLAIN), "Stop explaining yourself to them 👑 #shorts")
        self.assertEqual(seo.style_title("Only when you are useful 🌧", USEFUL), "Only when you are useful 😔 #shorts")

    def test_end_punctuation_goes_before_the_emoji_but_meaning_stays(self):
        self.assertEqual(seo.style_title(HEALED, HEALED), "My heart finally healed, and I didn't even notice when 🌱 #shorts")
        self.assertEqual(seo.style_title("Why do we pretend? 🖤", HEART), "Why do we pretend? 🖤 #shorts")
        self.assertTrue(seo.style_title("The best way to not get your heart...", HEART).startswith("The best way to not get your heart... "))
        long_title = "word " * 22
        self.assertEqual(seo.style_title(long_title, HEART), long_title)

    def test_an_emoji_the_gate_would_reject_as_a_template_is_avoided(self):
        recent = ["Older one 🖤 #shorts", "Older two 🖤 #shorts", "Older three 🖤 #shorts"]
        self.assertEqual(seo.repeated_emoji(recent), "🖤")
        self.assertEqual(seo.style_title("Pretending you don't have a heart", HEART, None, recent),
                         "Pretending you don't have a heart 🧊 #shorts")
        self.assertEqual(seo.repeated_emoji(recent[:2]), "")

    def test_the_whole_quote_leads_when_it_fits_and_short_titles_do_not(self):
        titles = seo.order_titles(["Stop explaining yourself 🛑", "Healing that arrives without warning 🌅"], HEALED)
        self.assertEqual(titles, ["My heart finally healed, and I didn't even notice when 🌱 #shorts",
                                  "Healing that arrives without warning 🌅 #shorts", "Stop explaining yourself 🌿 #shorts"])
        # The exact quote leads up to about 90 characters; the emojis rotate.
        titles = seo.order_titles(["Stop explaining yourself 🛑", "People who decided to misunderstand you 🛑"], EXPLAIN)
        self.assertEqual(titles, [f"{EXPLAIN[:-1]} 👑 #shorts", "People who decided to misunderstand you 💯 #shorts",
                                  "Stop explaining yourself 💪 #shorts"])
        self.assertTrue(all(len(title) <= 100 for title in titles))
        long_quote = "word " * 20 + "end."
        self.assertNotIn(long_quote.strip(), " ".join(seo.order_titles(["A different angle on it"], long_quote)))

    def test_a_near_verbatim_title_gives_way_to_the_exact_quote(self):
        misquote = "Stop explaining yourself to people who decided to misunderstand you 🥀"
        self.assertTrue(seo.near_verbatim(misquote, EXPLAIN))
        self.assertFalse(seo.near_verbatim(EXPLAIN, EXPLAIN))
        self.assertFalse(seo.near_verbatim("People who decided to misunderstand you", EXPLAIN))
        self.assertEqual(seo.order_titles([misquote, "Your peace is worth more than their opinion 🥀"], EXPLAIN),
                         [f"{EXPLAIN[:-1]} 👑 #shorts", "Your peace is worth more than their opinion 💯 #shorts"])

    def test_the_last_ai_shorts_emoji_is_skipped_while_another_fits(self):
        brief = {"exact_quote": PROUD, "ai_shorts": {**seo.quote_understanding(PROUD, {}), "recent_emojis": ["💪"]}}
        self.assertEqual(seo.style_title(PROUD, PROUD, brief), "Be proud of how hard you are trying 🔥 #shorts")


class HashtagTests(unittest.TestCase):
    def test_the_feeling_hashtag_follows_the_theme_and_tone(self):
        cases = {HEALED: "#healing", USEFUL: "#selfworth", PROUD: "#motivation", HEART: "#heartbreak",
                 DISCIPLINE: "#motivation", EXPLAIN: "#selfrespect",
                 "The quietest people usually have the loudest minds.": "#deepquotes"}
        for quote, feeling in cases.items():
            with self.subTest(quote=quote):
                self.assertEqual(seo.ai_short_hashtags(None, quote), ["#shorts", "#quotes", feeling])


class TagTests(unittest.TestCase):
    def test_typed_theme_phrases_become_the_tags_and_untyped_ones_are_dropped(self):
        client = FakeSuggest(untyped=("hiding",))
        brief = _brief(HEART, client)
        tags, evidence = seo.final_tags(brief, ["pretend", "yt", "shorts"], {}, quote=HEART)
        self.assertEqual(tags[-2:], ["yt", "shorts"])
        subject = tags[:-2]
        self.assertGreaterEqual(len(subject), 3)
        self.assertLessEqual(len(subject), seo.MAX_SUBJECT_TAGS)
        self.assertIn("heartbreak quotes", subject)
        self.assertNotIn("hiding feelings", subject)  # nobody types it
        self.assertNotIn("pretend", subject)  # a lone quote word is not a search
        self.assertTrue(all(len(tag.split()) >= 2 for tag in subject))
        rows = {row["keyword"]: row for row in evidence["selected_keywords"]}
        for tag in subject:
            self.assertTrue(rows[tag]["demand_validated"])
            self.assertEqual(rows[tag]["source_classification"], "combined")
            # Support is graded by how the theme ties to the quote, never a flat figure.
            relation = rows[tag]["relation_to_quote"]
            self.assertEqual(rows[tag]["source_support_score"], seo._RELATIONS[relation][0])
        self.assertEqual(rows["heartbreak quotes"]["relation_to_quote"], "quote_words")
        self.assertEqual(rows["heartbreak quotes"]["source_support_score"], 90)
        self.assertIn("checked against YouTube search suggestions", brief["ai_shorts"]["tag_note"])
        self.assertLessEqual(len(client.asked), 6)

    def test_specific_themes_come_before_broad_ones(self):
        tags, _ = seo.final_tags(_brief(USEFUL), [], {}, quote=USEFUL)
        self.assertEqual(tags[:4], ["fake people quotes", "being used quotes", "self worth quotes", "self respect quotes"])

    def test_without_suggestions_the_reading_is_kept_and_the_note_says_so(self):
        for client, words in ((Broken(), "could not be reached"), (FakeSuggest(status="disabled"), "turned off")):
            with self.subTest(words=words):
                brief = _brief(PROUD, client)
                self.assertIn(words, brief["ai_shorts"]["tag_note"])
                tags, evidence = seo.final_tags(brief, [], {}, quote=PROUD)
                self.assertGreaterEqual(len(tags) - 2, 3)
                rows = {row["keyword"]: row for row in evidence["selected_keywords"]}
                self.assertFalse(any(rows[tag].get("demand_validated") for tag in tags[:-2]))
                self.assertEqual({rows[tag]["source_classification"] for tag in tags[:-2]}, {"script_derived"})

    def test_a_quote_with_no_readable_theme_says_nothing_was_checked(self):
        client = FakeSuggest()
        verified = seo.verify_subject_tags({"search_themes": []}, quote="ஒரு நாள்", client=client)
        self.assertEqual(verified["subject_tags"], [])
        self.assertIn("No search theme could be read", verified["tag_note"])

    def test_the_shared_selectors_phrases_top_up_a_short_list_but_its_lone_words_never(self):
        brief = _brief(PROUD, FakeSuggest(untyped=("quotes", "motivation")))
        self.assertEqual(brief["ai_shorts"]["subject_tags"], [])
        tags, _ = seo.final_tags(brief, ["useful", "hard work quotes", "yt", "shorts"], {}, quote=PROUD)
        self.assertEqual(tags, ["hard work quotes", "yt", "shorts"])

    def test_fewer_than_three_subject_tags_is_not_green(self):
        gate = {"verdict": "GREEN", "warnings": [], "final_seo_quality": {"verdict": "GREEN", "warnings": []}}
        flagged = seo.flag_sparse_subject_tags(gate, ["heartbreak quotes", "pretend", "sad quotes", "yt", "shorts"])
        self.assertEqual((flagged["verdict"], flagged["final_seo_quality"]["verdict"]), ("YELLOW", "YELLOW"))
        self.assertEqual(flagged["warnings"][-1]["code"], "sparse_subject_tags")
        self.assertEqual(gate["verdict"], "GREEN")  # the caller's gate is not mutated
        kept = seo.flag_sparse_subject_tags(gate, ["heartbreak quotes", "broken heart quotes", "deep quotes", "yt", "shorts"])
        self.assertIs(kept, gate)
        # Filler searches every sad quote shares do not make a package GREEN.
        filler = seo.flag_sparse_subject_tags(gate, ["emotional quotes", "life quotes", "deep quotes", "sad reality quotes"])
        self.assertEqual(filler["verdict"], "YELLOW")
        self.assertTrue(seo.is_generic_tag("self motivation") and seo.is_generic_tag("hope quotes"))
        self.assertFalse(seo.is_generic_tag("sad love quotes") or seo.is_generic_tag("tamil sad quotes"))


def _plan(quote: str, direction: dict | None = None) -> dict:
    plan = {
        "quote": quote, "language": "english", "parts": 1, "total_seconds": 8,
        "mood": {"feeling": "quiet", "visual_metaphor": "a person walking alone at dusk", "keywords": []},
        "shots": [], "generation_source": "fallback", "provider": {}, "checks": {"passed": True},
    }
    if direction:
        plan["creative_direction"] = direction
    return plan


class PackageTests(unittest.TestCase):
    """The whole AI Shorts package stage, offline: Gemini off, the writer's local package, fake suggestions."""

    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.store = HistoryStore(str(Path(self.dir.name) / "seo.db"))
        self.patches = [
            patch.object(gemini_client, "is_available", return_value=False),
            patch.object(seo, "suggest_client", return_value=FakeSuggest(untyped=("hiding",))),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self) -> None:
        for item in self.patches:
            item.stop()
        self.dir.cleanup()

    def generate(self, quote: str, direction: dict | None = None) -> dict:
        with patch.object(ai_shorts, "_plan_flow_shots", return_value=_plan(quote, direction)):
            return ai_shorts.generate_ai_short(self.store, quote=quote, parts=1)

    def test_the_package_carries_the_readings_tags_hashtags_and_emoji(self):
        for quote, emoji, feeling in ((HEALED, "🌱", "#healing"), (USEFUL, "😔", "#selfworth"),
                                      (PROUD, "💪", "#motivation"), (HEART, "🖤", "#heartbreak")):
            with self.subTest(quote=quote):
                body = self.generate(quote)
                package = body["package"]
                subject = [tag for tag in package["tags"] if tag not in {"yt", "shorts"}]
                self.assertEqual(package["tags"][-2:], ["yt", "shorts"])
                self.assertGreaterEqual(len(subject), 3, package["tags"])
                self.assertTrue(all(len(tag.split()) >= 2 for tag in subject), subject)
                self.assertEqual(package["hashtags"], ["#shorts", "#quotes", feeling])
                self.assertTrue(package["description"].rstrip().endswith(f"#shorts #quotes {feeling}"))
                self.assertIn(quote, package["description"])
                # The exact quote, then a reflective line, then the hashtags.
                reflection = seo._flat_words(package["description"].replace(quote, " ")).split()
                self.assertGreaterEqual(len([word for word in reflection if word not in {"shorts", "quotes"}]), 4)
                self.assertTrue(package["title"].endswith(f"{emoji} #shorts"), package["title"])
                titles = [package["title"], *package["title_variants"]]
                for title in titles:
                    self.assertTrue(title.endswith(" #shorts") and len(title_emojis(title)) == 1, title)
                    self.assertLessEqual(len(title), 100)
                # The alternatives do not all share one emoji.
                if len(set(titles)) > 1:
                    self.assertGreater(len({title_emojis(title)[0] for title in titles}), 1, titles)
                self.assertNotIn("💔", package["title"])
                self.assertEqual(package["research_warnings"][0], ai_shorts.RESEARCH_SKIPPED_WARNING)
                self.assertIn("checked against YouTube search suggestions", package["research_warnings"][1])
                self.assertIn(package["generation_quality"]["verdict"], {"GREEN", "YELLOW"})
                # The saved run is the package the creator sees.
                run = self.store.history_run(body["analysis_run_id"])
                self.assertEqual(run["title"], package["title"])
                self.assertEqual(run["package"]["tags"], package["tags"])
                self.assertEqual(run["package"]["hashtags"], package["hashtags"])

    def test_a_short_whole_quote_leads_the_titles(self):
        package = self.generate(PROUD)["package"]
        self.assertEqual(package["title"], "Be proud of how hard you are trying 💪 #shorts")

    def test_the_planners_themes_lead_the_tags(self):
        direction = {"tone": "healing", "emotion": "quiet relief", "quote_meaning": "Healing and self growth came unnoticed.",
                     "search_themes": ["healing quotes", "moving on quotes", "self growth quotes"]}
        package = self.generate(HEALED, direction)["package"]
        self.assertEqual(package["tags"][:3], ["healing quotes", "moving on quotes", "self growth quotes"])
        self.assertEqual(package["creator_brief"]["ai_shorts"]["tone_source"], "planner")

    def test_a_package_left_with_too_few_tags_is_not_green(self):
        with patch.object(seo, "suggest_client", return_value=FakeSuggest(untyped=("quotes", "self", "motivation"))):
            package = self.generate(PROUD)["package"]
        subject = [tag for tag in package["tags"] if seo.meaningful_tag(tag)]
        self.assertLess(len(subject), 3)
        self.assertNotEqual(package["generation_quality"]["verdict"], "GREEN")
        codes = [item.get("code") for item in package["generation_quality"]["warnings"]]
        self.assertIn("sparse_subject_tags", codes)


class CreatorUnchangedTests(unittest.TestCase):
    def test_the_creator_path_never_enters_the_ai_shorts_branches(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("the Creator path must not use the AI Shorts SEO")

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(gemini_client, "is_available", return_value=False), \
                patch.object(seo, "final_tags", forbidden), patch.object(seo, "order_titles", forbidden), \
                patch.object(seo, "ai_short_hashtags", forbidden), patch.object(seo, "style_title", forbidden), \
                patch.object(seo, "flag_sparse_subject_tags", forbidden), patch.object(seo, "writer_guidance", forbidden):
            store = HistoryStore(str(Path(folder) / "creator.db"))
            brief = {"exact_quote": HEART, "on_screen_text": HEART, "video_format": "youtube_shorts",
                     "title_style": "balanced", "content": HEART}
            research = ai_shorts.lean_research(store, {**brief})
            package = generate_seo_suggestions(HEART, research, context={"language": "english", "creator_brief": brief})
        self.assertTrue(package["title"])
        self.assertNotIn("ai_shorts", package["creator_brief"])


SILENCE = "Silence is the best answer to someone who doesn't value your words."
MISS = "You can miss someone and still know you're better without them."
HOME = "Home is not a place, it's a person."


class RoundTwoReviewTests(unittest.TestCase):
    """The live review of sixteen quotes: the planner's reading leads, the tables only stand in for it."""

    def test_the_planners_hashtag_and_emojis_lead_when_they_fit(self):
        plan = {"creative_direction": {"tone": "calm", "hashtag": "SelfRespect", "emojis": ["🏆", "🛑", "🥀"]}}
        reading = seo.quote_understanding(SILENCE, plan)
        self.assertEqual(reading["planner_hashtag"], "#selfrespect")
        self.assertEqual(reading["planner_emojis"], ["🏆"])  # 🛑 is literal; 🥀 is against a calm tone
        brief = {"exact_quote": SILENCE, "ai_shorts": reading}
        self.assertEqual(seo.ai_short_hashtags(brief, SILENCE)[-1], "#selfrespect")
        self.assertTrue(seo.style_title("The best answer", SILENCE, brief).endswith("🏆 #shorts"))
        # Not a feeling hashtag, or one against the tone: the quote's theme, then its tone, stand in.
        for hashtag in ("#viral", "#motivation", "not a hashtag!"):
            with self.subTest(hashtag=hashtag):
                reading = seo.quote_understanding(TIRED, {"creative_direction": {"tone": "sad", "hashtag": hashtag}})
                self.assertEqual(reading["planner_hashtag"], "")
                self.assertEqual(seo.ai_short_hashtags({"ai_shorts": reading}, TIRED)[-1], "#sadquotes")

    def test_the_reviewed_hashtags_without_a_planner_reading(self):
        cases = {SILENCE: "#selfrespect", MISS: "#movingon", HOME: "#love"}
        for quote, hashtag in cases.items():
            with self.subTest(quote=quote):
                self.assertEqual(seo.ai_short_hashtags(None, quote)[-1], hashtag)
        # The quote's own theme wins over a planner search theme about heartbreak.
        plan = {"creative_direction": {"tone": "sad",
                                       "search_themes": ["heartbreak quotes", "fake love quotes", "being used quotes"]}}
        brief = {"ai_shorts": seo.quote_understanding(USEFUL, plan)}
        self.assertEqual(seo.ai_short_hashtags(brief, USEFUL)[-1], "#selfworth")

    def test_the_reviewed_emojis_come_from_the_theme_before_the_tone(self):
        cases = {SILENCE: "👑", EXPLAIN: "👑", HOME: "❤️"}
        for quote, emoji in cases.items():
            with self.subTest(quote=quote):
                self.assertTrue(seo.style_title("A title", quote).endswith(f"{emoji} #shorts"))
        # Discipline read as hopeful by the planner is still effort, not a sunrise.
        hopeful = {"ai_shorts": seo.quote_understanding(DISCIPLINE, {"creative_direction": {"tone": "hopeful"}})}
        self.assertTrue(seo.style_title("A title", DISCIPLINE, hopeful).endswith("💪 #shorts"))

    def test_a_tamil_or_tanglish_short_gets_tamil_searches_and_tamilquotes(self):
        for language in ("tamil", "tanglish"):
            with self.subTest(language=language):
                reading = seo.quote_understanding(TIRED, {"creative_direction": {"tone": "sad"}}, language=language)
                self.assertEqual(reading["search_themes"][:2], ["tamil sad quotes", "tamil quotes"])
                brief = {"ai_shorts": reading}
                self.assertEqual(seo.ai_short_hashtags(brief, TIRED), ["#shorts", "#tamilquotes", "#sadquotes"])
                verified = seo.verify_subject_tags(reading, quote=TIRED, language=language, client=FakeSuggest())
                self.assertEqual([row["keyword"] for row in verified["subject_tags"]][:2],
                                 ["tamil sad quotes", "tamil quotes"])
        self.assertEqual(seo.ai_short_hashtags(None, TIRED)[1], "#quotes")

    def test_an_exact_quote_title_up_to_90_characters_is_not_downgraded_and_keyword_noise_goes(self):
        title = f"{EXPLAIN[:-1]} 👑 #shorts"
        noise = {"code": "primary_keyword_missing_from_title", "field": "title", "severity": "info", "message": "x"}
        band = {"code": "title_length_outside_band", "field": "title", "severity": "warning", "message": "x"}
        gate = {"verdict": "YELLOW", "passed": True, "warnings": [noise, band],
                "final_seo_quality": {"verdict": "YELLOW", "warnings": [noise, band]}}
        tags = ["self respect quotes", "misunderstood quotes", "attitude quotes", "yt", "shorts"]
        final = seo.finalize_gate(gate, title, tags, EXPLAIN)
        self.assertEqual((final["verdict"], final["final_seo_quality"]["verdict"]), ("GREEN", "GREEN"))
        self.assertEqual(final["warnings"], [])
        # A paraphrase keeps the band warning, and any other warning still holds the verdict.
        paraphrase = "A paraphrase of the quote that runs long 👑 #shorts"
        self.assertEqual(seo.finalize_gate(gate, paraphrase, tags, EXPLAIN)["verdict"], "YELLOW")
        other = {"code": "title_duplicates_on_screen_quote", "field": "title", "severity": "warning", "message": "x"}
        held = {**gate, "final_seo_quality": {"verdict": "YELLOW", "warnings": [band, other]}}
        self.assertEqual(seo.finalize_gate(held, title, tags, EXPLAIN)["verdict"], "YELLOW")


class RecentScenesTests(unittest.TestCase):
    def test_recent_scenes_reach_a_planner_that_accepts_them(self):
        from win_engine.feedback.ai_shorts_store import AiShortsStore
        from win_engine.generation import flow_prompts

        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(str(Path(folder) / "s.db"))
            plans = AiShortsStore(store)
            for index, plan in enumerate((
                {"creative_direction": {"scene": "A figure walks up a grassy hill at golden hour"}},
                {"shots": [{"title": "Window at dusk"}, {"title": "Window at dusk"}]},
            )):
                run = store.record_analysis_run(f"q{index}", "browse", "quote", f"T{index}", 1.0, "LOW",
                                                "UNMEASURED", None, {})
                plans.save_plan(analysis_run_id=run, quote=f"q{index}", language="english", parts=1, plan=plan,
                                package={})
            recent = ["Window at dusk", "A figure walks up a grassy hill at golden hour"]
            self.assertEqual(plans.recent_scenes(10), recent)

            seen: list = []

            def accepts(quote, *, language, parts, mood_hint, creative_direction, avoid_scenes=()):
                seen.append(list(avoid_scenes))
                return _plan(quote)

            def older(quote, *, language, parts, mood_hint, creative_direction):
                seen.append("called without avoid_scenes")
                return _plan(quote)

            for planner, expected in ((accepts, recent), (older, "called without avoid_scenes")):
                seen.clear()
                with patch.object(flow_prompts, "plan_flow_shots", planner), \
                        patch.object(gemini_client, "is_available", return_value=False), \
                        patch.object(seo, "suggest_client", return_value=FakeSuggest()):
                    ai_shorts.generate_ai_short(store, quote=PROUD, parts=1)
                self.assertEqual(seen[0], expected)

GOODBYE = "You were my favorite hello and my hardest goodbye."


class RoundThreeReviewTests(unittest.TestCase):
    """The final review of 22 quotes."""

    def test_a_platform_tag_in_the_prose_never_reaches_the_description(self):
        leaked = f"{GOODBYE} Sitting with the heavy quiet after someone wonderful becomes a memory. yt\n\n#shorts #quotes #heartbreak"
        cleaned = seo.strip_platform_words(leaked, GOODBYE)
        self.assertNotIn(" yt", cleaned)
        self.assertTrue(cleaned.endswith("becomes a memory.\n\n#shorts #quotes #heartbreak"))
        self.assertEqual(seo.strip_platform_words(f"{GOODBYE}\nyt shorts", GOODBYE), GOODBYE)
        self.assertNotIn("yt", seo.with_reflection(leaked, GOODBYE))
        reply = json.dumps({
            "title": GOODBYE, "variants": [GOODBYE, "The goodbye that still hurts the most", "My hardest goodbye"],
            "description": f"{GOODBYE} Every hello carries its goodbye somewhere inside it. yt",
            "tags": ["goodbye quotes"], "hashtags": ["#shorts", "#quotes", "#heartbreak"],
        })
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(gemini_client, "is_available", return_value=True), \
                patch.object(gemini_client, "generate", return_value=reply), \
                patch.object(seo, "suggest_client", return_value=FakeSuggest()), \
                patch.object(ai_shorts, "_plan_flow_shots", return_value=_plan(GOODBYE)):
            package = ai_shorts.generate_ai_short(HistoryStore(str(Path(folder) / "y.db")), quote=GOODBYE, parts=1)["package"]
        self.assertNotRegex(package["description"], r"(?<![#\w])yt\b")
        self.assertIn("Every hello carries its goodbye somewhere inside it.", package["description"])

    def test_only_feeling_emojis_are_taken_from_the_planner(self):
        reading = seo.quote_understanding(HEART, {"creative_direction": {"tone": "numb", "emojis": ["🪵", "🏔️", "🖤"]}})
        self.assertEqual(reading["planner_emojis"], ["🖤"])
        storm = seo.quote_understanding("The storm passed and I am still here.",
                                        {"creative_direction": {"tone": "hopeful", "emojis": ["🏔️", "🌊"]}})
        self.assertEqual(storm["planner_emojis"], [])
        self.assertNotIn("🏔", seo.style_title("Still here after the storm", "The storm passed and I am still here.",
                                               {"ai_shorts": storm}))

    def test_a_planner_hashtag_is_used_only_when_viewers_follow_or_type_it(self):
        def hashtag(quote, tone, proposed, typed=()):
            reading = seo.quote_understanding(quote, {"creative_direction": {"tone": tone, "hashtag": proposed}})
            reading["search_demand"] = {"validated_keywords": list(typed)}
            return seo.ai_short_hashtags({"ai_shorts": reading}, quote)[-1]

        self.assertEqual(hashtag(HEART, "numb", "#emotionalwall"), "#heartbreak")
        self.assertEqual(hashtag(HOME, "romantic", "#longing"), "#love")
        self.assertEqual(hashtag(HOME, "romantic", "#longing", typed=["longing quotes"]), "#longing")
        self.assertEqual(hashtag(MISS, "bittersweet", "#lifequotes"), "#movingon")
        self.assertEqual(hashtag(HEALED, "healing", "#selflove"), "#selflove")

    def test_the_quotes_own_subjects_are_tried_as_searches(self):
        cases = {
            "My mother is the reason I never gave up.": "mother quotes",
            "Good friends are hard to find and harder to leave.": "friendship quotes",
            "Protect your energy from people who drain it.": "positive energy quotes",
        }
        for quote, phrase in cases.items():
            with self.subTest(quote=quote):
                reading = seo.quote_understanding(quote, {"creative_direction": {"tone": "uplifting",
                                                                               "search_themes": ["life lesson quotes"]}})
                self.assertIn(phrase, reading["search_themes"][:6])
        for phrase in ("nostalgic quotes", "heartfelt quotes", "memories quotes", "emotional quotes"):
            self.assertTrue(seo.is_generic_tag(phrase), phrase)

    def test_a_hindi_or_hinglish_short_gets_shayari_searches_and_hindiquotes(self):
        for language in ("hindi", "hinglish"):
            with self.subTest(language=language):
                reading = seo.quote_understanding(TIRED, {"creative_direction": {"tone": "sad"}}, language=language)
                self.assertEqual(reading["search_themes"][:3], ["hindi shayari", "hindi sad quotes", "hindi quotes"])
                self.assertEqual(seo.ai_short_hashtags({"ai_shorts": reading}, TIRED)[:2], ["#shorts", "#hindiquotes"])

    def test_a_package_always_offers_three_title_options(self):
        titles = seo.order_titles([GOODBYE], GOODBYE)
        self.assertEqual(len(titles), 3)
        self.assertTrue(seo.is_exact_quote(titles[0], GOODBYE))
        self.assertTrue(any(title.startswith("My hardest goodbye ") for title in titles))
        self.assertEqual(seo.quote_clauses("Breathe."), [])

    def test_the_package_stage_has_room_for_the_writers_repair(self):
        self.assertEqual((ai_shorts.PLANNER_MAX_CALLS, ai_shorts.PACKAGE_MAX_CALLS, ai_shorts.MAX_GEMINI_CALLS), (3, 3, 6))

SPORTS = ["football quotes", "cricket quotes", "basketball quotes"]


class RelatednessTests(unittest.TestCase):
    """A suggestion proves a phrase exists, not that it fits the quote."""

    def test_unrelated_planner_themes_never_become_tags_even_when_typed(self):
        # The external review's reproduction: a heartbreak quote, three sports
        # themes and one valid theme, and a suggest client that confirms all.
        direction = {"tone": "heartbroken", "search_themes": [*SPORTS, "heartbreak quotes"]}
        reading = seo.quote_understanding(HEART, {"creative_direction": direction})
        verified = seo.verify_subject_tags(reading, quote=HEART, client=FakeSuggest())
        names = [row["keyword"] for row in verified["subject_tags"]]
        self.assertFalse(set(SPORTS) & set(names), names)
        self.assertIn("heartbreak quotes", names)
        self.assertEqual({item["keyword"] for item in verified["rejected_themes"]}, set(SPORTS))
        self.assertEqual({item["reason"] for item in verified["rejected_themes"]}, {"unrelated_to_quote"})
        for row in verified["subject_tags"]:
            self.assertIn(row["relation_to_quote"], seo._RELATIONS)
            self.assertEqual(row["source_support_score"], seo._RELATIONS[row["relation_to_quote"]][0])
        brief = {"exact_quote": HEART, "ai_shorts": {**reading, **verified}}
        tags, evidence = seo.final_tags(brief, [], {}, quote=HEART)
        self.assertFalse(set(SPORTS) & set(tags))
        self.assertTrue(set(SPORTS) <= {item["keyword"] for item in evidence["rejected_candidates"]
                                        if item["reason"] == "unrelated_to_quote"})

    def test_the_whole_package_rejects_them_and_its_tag_score_is_not_inflated(self):
        direction = {"tone": "heartbroken", "search_themes": [*SPORTS, "heartbreak quotes"]}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(gemini_client, "is_available", return_value=False), \
                patch.object(seo, "suggest_client", return_value=FakeSuggest()), \
                patch.object(ai_shorts, "_plan_flow_shots", return_value=_plan(HEART, direction)):
            package = ai_shorts.generate_ai_short(HistoryStore(str(Path(folder) / "r.db")), quote=HEART, parts=1)["package"]
        self.assertFalse(set(SPORTS) & set(package["tags"]), package["tags"])
        research = package["keyword_research"]
        selected = [row for row in research["selected_keywords"] if row.get("classification") != "platform_format"]
        self.assertFalse(set(SPORTS) & {row["keyword"] for row in selected})
        self.assertTrue(set(SPORTS) <= {item["keyword"] for item in research["rejected_candidates"]
                                        if item.get("reason") == "unrelated_to_quote"})
        scores = [float(row["keyword_relevance_score"]) for row in selected]
        self.assertEqual(package["generation_quality"]["final_seo_quality"]["tag_score"],
                         round(sum(scores) / len(scores), 1))

    def test_the_shared_selectors_unrelated_top_ups_are_refused(self):
        brief = _brief(PROUD, FakeSuggest(untyped=("quotes", "motivation")))
        tags, evidence = seo.final_tags(brief, ["football quotes", "hard work quotes", "yt", "shorts"], {}, quote=PROUD)
        self.assertEqual(tags, ["hard work quotes", "yt", "shorts"])
        self.assertIn({"keyword": "football quotes", "reason": "unrelated_to_quote", "source": "shared_selector"},
                      evidence["rejected_candidates"])

    def test_each_kind_of_tie_is_graded(self):
        reading = seo.quote_understanding(HEART, {"creative_direction": {
            "tone": "numb", "quote_meaning": "Hiding vulnerability to avoid emotional pain.", "emotion": "guarded"}},
            language="tamil")
        self.assertEqual(seo.theme_relation("broken heart quotes", reading, HEART), "quote_words")
        self.assertEqual(seo.theme_relation("vulnerability quotes", reading, HEART), "planner_reading")
        self.assertEqual(seo.theme_relation("tamil sad quotes", reading, HEART), "language")
        # Graded by the weakest word: "emotional" is the reading's, "numbness" only the niche's.
        self.assertEqual(seo.theme_relation("emotional numbness", reading, HEART), "quote_niche")
        self.assertEqual(seo.theme_relation("emotional pain quotes", reading, HEART), "planner_reading")
        self.assertEqual(seo.theme_relation("sad quotes", reading, HEART), "quote_niche")
        self.assertEqual(seo.theme_relation("football quotes", reading, HEART), "")
        hindi = seo.quote_understanding(TIRED, {"creative_direction": {"tone": "sad"}}, language="hindi")
        self.assertEqual(seo.theme_relation("hindi shayari", hindi, TIRED), "language")


class SuggestLimitTests(unittest.TestCase):
    def test_ai_shorts_uses_its_own_configured_limit_exactly(self):
        from win_engine.core.config import Settings

        for limit, enabled in ((4, True), (0, False), (12, True)):
            with self.subTest(limit=limit):
                settings = Settings(ai_shorts_suggest_max_queries=limit, search_suggest_max_queries=6,
                                    search_suggest_enabled=True)
                with patch("win_engine.core.config.get_settings", return_value=settings):
                    client = seo.suggest_client()
                self.assertEqual((client._max_queries, client.enabled), (limit, enabled))
                self.assertEqual(settings.search_suggest_max_queries, 6)
        off = Settings(ai_shorts_suggest_max_queries=10, search_suggest_enabled=False)
        with patch("win_engine.core.config.get_settings", return_value=off):
            self.assertFalse(seo.suggest_client().enabled)
        self.assertEqual(Settings().ai_shorts_suggest_max_queries, 10)

MEDICAL = ["heart surgery quotes", "heart disease quotes", "heart transplant quotes"]


class WholePhraseTests(unittest.TestCase):
    """One word shared with the quote does not make a phrase about it."""

    def test_heart_themes_from_another_domain_are_rejected_end_to_end(self):
        # The external review's case: the heartbreak quote, three medical
        # "heart" themes and one valid theme, and a suggest client that confirms all.
        direction = {"tone": "heartbroken", "search_themes": [*MEDICAL, "heartbreak quotes"]}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(gemini_client, "is_available", return_value=False), \
                patch.object(seo, "suggest_client", return_value=FakeSuggest()), \
                patch.object(ai_shorts, "_plan_flow_shots", return_value=_plan(HEART, direction)):
            package = ai_shorts.generate_ai_short(HistoryStore(str(Path(folder) / "m.db")), quote=HEART, parts=1)["package"]
        self.assertFalse(set(MEDICAL) & set(package["tags"]), package["tags"])
        self.assertIn("heartbreak quotes", package["tags"])
        research = package["keyword_research"]
        selected = [row for row in research["selected_keywords"] if row.get("classification") != "platform_format"]
        self.assertFalse(set(MEDICAL) & {row["keyword"] for row in selected})
        self.assertTrue(set(MEDICAL) <= {item["keyword"] for item in research["rejected_candidates"]
                                         if item.get("reason") == "unrelated_to_quote"})
        scores = [float(row["keyword_relevance_score"]) for row in selected]
        self.assertEqual(package["generation_quality"]["final_seo_quality"]["tag_score"],
                         round(sum(scores) / len(scores), 1))

    def test_every_topic_word_must_be_grounded_or_the_niches(self):
        reading = seo.quote_understanding(HEART, {})
        for theme in MEDICAL:
            with self.subTest(theme=theme):
                self.assertEqual(seo.theme_relation(theme, reading, HEART), "")
        self.assertEqual(seo.theme_relation("broken heart quotes", reading, HEART), "quote_words")
        self.assertEqual(seo.theme_relation("heartbreak quotes", reading, HEART), "quote_words")
        self.assertEqual(seo.theme_relation("emotional numbness", reading, HEART), "quote_niche")
        mother = "My mother taught me to stand up again."
        self.assertEqual(seo.theme_relation("mother daughter quotes", seo.quote_understanding(mother, {}), mother),
                         "quote_niche")
        self.assertEqual(seo.theme_relation("football quotes", reading, HEART), "")
        self.assertEqual(seo.theme_relation("heart health tips", reading, HEART), "")

    def test_law_of_attraction_is_kept_only_for_a_quote_about_attracting(self):
        # Decision: "law" is not a quote-niche word, but "law of attraction" is
        # the niche's established phrase. It is kept (at the niche grade) when
        # the quote or its reading speaks of attracting, and rejected otherwise.
        attract = "What you think about, you attract into your life."
        self.assertEqual(seo.theme_relation("law of attraction quotes", seo.quote_understanding(attract, {}), attract),
                         "quote_niche")
        self.assertEqual(seo.theme_relation("law of attraction quotes", seo.quote_understanding(HEART, {}), HEART), "")

LOVE_KILLS = "There are plenty of ways to die, but only love can kill and keep you alive to feel it."
LOVE_KILLS_DIRECTION = {
    "tone": "heartbroken", "hashtag": "#love", "emojis": ["❤️", "🌅", "🌾"],
    "search_themes": ["love quotes", "deep love quotes", "romantic quotes", "relationship quotes"],
}
PAINFUL_LOVE = {"love hurts quotes", "painful love quotes", "sad love quotes", "heartbreak quotes"}
PAIN_EMOJIS = {"💔", "🥀", "😢"}


class ToneConsistencyTests(unittest.TestCase):
    """Love that hurts is packaged as pain, a love that does not as love."""

    def _brief(self, quote, direction, client=None):
        reading = seo.quote_understanding(quote, {"creative_direction": direction})
        verified = seo.verify_subject_tags(reading, quote=quote, client=client or FakeSuggest())
        return {"exact_quote": quote, "ai_shorts": {**reading, **verified}}

    def test_love_that_hurts_gets_painful_love_tags_hashtag_and_emoji(self):
        brief = self._brief(LOVE_KILLS, LOVE_KILLS_DIRECTION)
        tags, evidence = seo.final_tags(brief, ["romantic quotes"], {}, quote=LOVE_KILLS)
        self.assertNotIn("romantic quotes", tags)
        self.assertTrue(PAINFUL_LOVE & set(tags), tags)
        self.assertIn({"keyword": "romantic quotes", "reason": "contradicts_tone", "source": "ai_shorts_theme"},
                      evidence["rejected_candidates"])
        # The shared selector's top-ups (considered below three tags) obey the tone too.
        bare = {"exact_quote": LOVE_KILLS, "ai_shorts": {**brief["ai_shorts"], "subject_tags": []}}
        topped, topped_evidence = seo.final_tags(bare, ["romantic quotes", "painful love quotes"], {}, quote=LOVE_KILLS)
        self.assertEqual(topped, ["painful love quotes", "yt", "shorts"])
        self.assertIn({"keyword": "romantic quotes", "reason": "contradicts_tone", "source": "shared_selector"},
                      topped_evidence["rejected_candidates"])
        # Viewers type "love hurts quotes" here, so #lovehurts; otherwise #heartbreak, never #love.
        self.assertEqual(seo.ai_short_hashtags(brief, LOVE_KILLS)[-1], "#lovehurts")
        untyped = self._brief(LOVE_KILLS, LOVE_KILLS_DIRECTION, FakeSuggest(untyped=("love hurts",)))
        self.assertEqual(seo.ai_short_hashtags(untyped, LOVE_KILLS)[-1], "#heartbreak")
        self.assertEqual(brief["ai_shorts"]["planner_emojis"], [])  # ❤️ and 🌅 are warm, 🌾 is the footage
        self.assertIn(title_emojis(seo.style_title("Only love can kill", LOVE_KILLS, brief))[0], PAIN_EMOJIS)
        self.assertTrue(seo.contradicts_tone("good vibes quotes", "sad"))
        self.assertTrue(seo.contradicts_tone("broken heart quotes", "hopeful"))
        self.assertFalse(seo.contradicts_tone("deep love quotes", "heartbroken"))

    def test_a_love_that_does_not_hurt_keeps_love(self):
        direction = {"tone": "romantic", "hashtag": "#love", "emojis": ["❤️"],
                     "search_themes": ["love quotes", "home quotes", "sad love quotes", "soulmate quotes"]}
        brief = self._brief(HOME, direction)
        tags, _ = seo.final_tags(brief, [], {}, quote=HOME)
        self.assertIn("love quotes", tags)
        self.assertNotIn("sad love quotes", tags)
        self.assertEqual(seo.ai_short_hashtags(brief, HOME)[-1], "#love")
        self.assertTrue(seo.style_title("Home is a person", HOME, brief).endswith("❤️ #shorts"))

    def test_the_delivered_package_and_its_trace_agree(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(gemini_client, "is_available", return_value=False), \
                patch.object(seo, "suggest_client", return_value=FakeSuggest()), \
                patch.object(ai_shorts, "_plan_flow_shots", return_value=_plan(LOVE_KILLS, LOVE_KILLS_DIRECTION)):
            package = ai_shorts.generate_ai_short(HistoryStore(str(Path(folder) / "l.db")), quote=LOVE_KILLS,
                                                  parts=1)["package"]
        self.assertNotIn("romantic quotes", package["tags"])
        self.assertTrue(PAINFUL_LOVE & set(package["tags"]), package["tags"])
        self.assertIn(package["hashtags"][-1], {"#heartbreak", "#lovehurts"})
        self.assertIn(title_emojis(package["title"])[0], PAIN_EMOJIS)
        trace = package["generation_trace"]
        self.assertEqual(trace["final_tags"], package["tags"])
        self.assertEqual([item["tag"] for item in trace["final_tag_provenance"]], package["tags"])
        self.assertEqual([item["keyword"] for item in trace["final_tag_scores"]], package["tags"])

if __name__ == "__main__":
    unittest.main()
