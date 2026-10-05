"""The quote Short package contract, as the creator pastes it to YouTube.

The channel posts English quote Shorts (a quote over calm footage). YouTube's
guidance: titles accurate and compelling; tags "play a minimal role"; #shorts
in a title is not required, since Shorts are detected by format; the first
three description hashtags show above the title. So a title may be the quote
or its punchline but never cuts it, stops before its turn or reverses it;
tags and hashtags are advisory and never fail a package; and the verdict is
honest: unsafe is RED, weak or sparse is YELLOW, clean and complete is GREEN.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.generation_quality import (
    _hashtag_length,
    evaluate_package_quality,
    feeling_hashtag,
    focused_short_hashtags,
    quote_title_issues,
    safe_quote_title,
    title_reverses_quote,
)
from win_engine.analysis.keyword_research import (
    build_keyword_research,
    natural_tag_phrase,
    select_final_tags,
    tag_length,
)
from win_engine.analysis.source_cues import quote_punchline
from win_engine.generation.strategy_engine import _content_specific_fallback, _feeling_emoji
from win_engine.llm import seo_writer


def _codes(title: str, quote: str) -> set[str]:
    return {issue["code"] for issue in quote_title_issues(title, quote)}


class QuoteTitleChecksTests(unittest.TestCase):
    def test_the_whole_quote_and_its_punchline_pass(self):
        quote = "Some people keep you close enough to need you, but never close enough to choose you"
        self.assertEqual(_codes(quote, quote), set())
        self.assertEqual(_codes("Never close enough to choose you 💔", quote), set())

    def test_a_title_that_stops_before_the_turn_or_cuts_the_quote_fails(self):
        quote = "Some people keep you close enough to need you, but never close enough to choose you"
        self.assertIn("missing_quote_payoff", _codes("Some people keep you close enough to need you", quote))
        self.assertIn("quote_title_cut", _codes("Some people keep you close enough to...", quote))
        # A comparison and a relative clause are what the words before them are about.
        self.assertIn("quote_title_cut", _codes(
            "There is nothing more painful in this world",
            "There is nothing more painful in this world than to be in love with something that never can be",
        ))
        self.assertIn("quote_title_cut", _codes(
            "Pay attention to the ones",
            "in a world where people always want something from you, pay attention to the ones who just want you",
        ))
        # A scene-setting opening is the setup; the main clause is the point.
        self.assertIn("missing_quote_payoff", _codes(
            "In a world where people always want something from you",
            "in a world where people always want something from you, pay attention to the ones who just want you",
        ))
        # The punchline needs no new words to be the point.
        quote = ("There was before you and there was during you. For some reason, I never thought there would "
                 "be an after you. But there was, and I was in it.")
        self.assertIn("missing_quote_payoff", _codes("For some reason, I never thought there would be an after you", quote))

    def test_a_title_that_negates_or_reverses_the_quote_fails(self):
        self.assertTrue(title_reverses_quote("Why I finally stopped loving you", "I never stopped loving you"))
        self.assertIn("reversed_quote_meaning", _codes("Why I finally stopped loving you", "I never stopped loving you"))
        # The negation may move to another word.
        self.assertFalse(title_reverses_quote(
            "Giving up on someone never happens overnight", "You don't give up overnight on someone",
        ))
        # A word the quote both denies and affirms is reversed by neither use.
        self.assertFalse(title_reverses_quote(
            "It's more about who makes you feel seen",
            "It's not about who knows you the longest, but it's more about who makes you feel seen",
        ))

    def test_a_keyword_quotes_construction_fails(self):
        quote = "Stop explaining yourself to people who already decided to misunderstand you"
        self.assertIn("keyword_quotes_title", _codes("Alone quotes for when people misunderstand you", quote))

    def test_shorts_hashtag_and_emoji_are_optional(self):
        quote = "Some people are meant to be remembered, not kept"
        package = {
            "title": "Some people are meant to be remembered, not kept",
            "variants": ["Some people are meant to be remembered, not kept",
                         "Remembered, never kept: some people stay that way #shorts"],
            "description": f"“{quote}”", "tags": ["being remembered"], "hashtags": ["#shorts", "#quotes"],
        }
        gate = evaluate_package_quality(package, script=quote, creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"})
        self.assertEqual(len(gate["accepted_candidates"]), 2)
        self.assertNotIn("missing_shorts_title_hashtag", {issue["code"] for row in gate["rejected_candidates"] for issue in row["issues"]})


class QuoteTitleChoiceTests(unittest.TestCase):
    CASES = {
        # Whole when it fits: a few characters over 70 beat a cut.
        "Some people keep you close enough to need you, but never close enough to choose you":
            "Some people keep you close enough to need you, but never close enough to choose you",
        # A relative clause keeps the noun it describes.
        "the older I get, the more i realise how rare it is to have someone who has seen every version of you and still stayed":
            "Someone who has seen every version of you and still stayed",
        # The main clause after a scene-setting opening.
        "in a world where people always want something from you, pay attention to the ones who just want you":
            "Pay attention to the ones who just want you",
        # What a comparison names stands alone; "than ..." never does.
        "There is nothing more painful in this world than to be in love with something that never can be yours":
            "To be in love with something that never can be yours",
        # What the quote says you notice.
        "As you get older, you notice how people really do make time for the things they love & excuses for the things they don't":
            "People really do make time for the things they love & excuses for the things they don't",
    }

    def test_a_quote_becomes_a_complete_title_that_keeps_its_point(self):
        for quote, expected in self.CASES.items():
            with self.subTest(quote=quote):
                title = safe_quote_title(quote)
                self.assertEqual(title, expected)
                self.assertNotIn("…", title)
                self.assertNotIn("...", title)
                self.assertNotIn("#shorts", title.casefold())
                self.assertEqual(_codes(title, quote), set())

    def test_a_quote_with_the_creators_keywords_pasted_after_it(self):
        script = ("maybe when your ego finally goes quiet you'll, when your ego finally goes quiet, understanding what "
                  "you lost, quotes about ego and pride, quiet emotional quotes, regret and stubbornness, aesthetic "
                  "night shorts, deep realization quotes, shorts, yt, youtube shorts, viral shorts")
        brief = build_creator_brief(script=script)
        self.assertEqual(brief["exact_quote"], "maybe when your ego finally goes quiet you'll, when your ego finally goes "
                                               "quiet, understanding what you lost")

    def test_the_quote_is_read_from_unpunctuated_and_glued_labels(self):
        brief = build_creator_brief(script="Background is sunset in beach and the quote on the screen is And why is it "
                                           "always that if someone offers me a flower, I offer them my entire garden??")
        self.assertEqual(brief["exact_quote"], "And why is it always that if someone offers me a flower, I offer them my entire garden??")
        brief = build_creator_brief(script="the quote is- There is nothing more painful in this world than to be in "
                                           "love with something that never can be yours.and video is a girl looking at the moon")
        self.assertTrue(brief["exact_quote"].endswith("never can be yours"))


class QuoteFallbackTests(unittest.TestCase):
    def test_the_fallback_is_the_quote_its_feeling_and_followed_hashtags(self):
        quote = "You can miss someone and still know you're better without them"
        brief = build_creator_brief(
            script=f"the quote on the screen is {quote}. and video is a man walking through green hills",
            video_format="youtube_shorts",
            viewer_promise="Deep emotional resonance, relatable truth, and life perspective",
        )
        package = _content_specific_fallback(brief["topic"], [], brief)
        self.assertEqual(package["title"], f"{quote} 🥀")
        # Only the quote: the brief's prose is not a line about this quote.
        self.assertEqual(package["description"], f"“{quote}”")
        self.assertEqual(package["hashtags"], ["#shorts", "#quotes", "#missingyou"])
        self.assertTrue(all(len(tag) <= 30 and natural_tag_phrase(tag) for tag in package["tags"]))
        self.assertFalse(any("resonance" in tag for tag in package["tags"]))

    def test_a_creator_line_about_the_quote_is_kept_as_its_second_line(self):
        quote = "You can miss someone and still know you're better without them"
        promise = "A relatable reminder that missing someone does not mean they belong in your life"
        brief = build_creator_brief(script=f"On-screen quote: '{quote}'", video_format="youtube_shorts", viewer_promise=promise)
        package = _content_specific_fallback(brief["topic"], [], brief)
        self.assertEqual(package["description"], f"“{quote}”\n\n{promise}.")


class HonestVerdictTests(unittest.TestCase):
    QUOTE = "Some people are meant to be remembered, not kept"

    def gate(self, script: str | None = None, **package):
        quote = self.QUOTE if script is None else script
        base = {
            "title": self.QUOTE,
            "variants": [self.QUOTE, "Remembered, never kept: some people stay that way",
                         "The people we remember are not always the ones we keep"],
            "description": f"“{self.QUOTE}”\n\nSome goodbyes are a kind of keeping.",
            "tags": ["being remembered", "shorts"], "hashtags": ["#shorts", "#quotes"],
        }
        base.update(package)
        return evaluate_package_quality(base, script=quote, creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"})

    def test_a_clean_complete_package_is_green(self):
        self.assertEqual(self.gate()["verdict"], "GREEN")

    def test_a_quote_only_fallback_is_yellow_not_red(self):
        gate = self.gate(variants=[self.QUOTE], description=f"“{self.QUOTE}”")
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["verdict"], "YELLOW")
        self.assertIn("title_duplicates_on_screen_quote", {item["code"] for item in gate["final_seo_quality"]["warnings"]})

    def test_a_one_word_quote_is_yellow_not_red(self):
        gate = self.gate(script="Breathe.", title="Breathe", variants=["Breathe"], description="“Breathe.”", tags=["shorts"])
        self.assertTrue(gate["passed"], gate["issues"])
        self.assertEqual(gate["verdict"], "YELLOW")

    def test_a_package_left_without_a_subject_tag_is_yellow_not_red(self):
        gate = self.gate(tags=["yt", "viral shorts", "crypto trading"])
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["verdict"], "YELLOW")
        self.assertIn("non_contextual_tags", {item["code"] for item in gate["warnings"]})

    def test_a_misquote_or_an_invented_claim_is_red(self):
        self.assertEqual(self.gate(description="Some people are meant to be remembered.")["verdict"], "RED")
        self.assertEqual(self.gate(title="They left because I asked for more", variants=[])["verdict"], "RED")

    def test_a_silence_quote_cannot_be_sold_as_comfort_but_a_love_quote_may_say_love(self):
        silence = "At the end, it's only me and the silence that knows everything."
        gate = self.gate(script=silence, title=silence, variants=[], description=f"“{silence}”\n\nA moment of comfort and peace.")
        self.assertIn("unsupported_context", {item["code"] for item in gate["issues"]})
        love = "Loving you was the easiest thing I ever did"
        gate = self.gate(script=love, title=love, variants=[], description=f"“{love}”\n\nSome love asks for nothing.")
        self.assertNotIn("unsupported_context", {item["code"] for item in gate["issues"]})
        gate = self.gate(script=love, title=love, variants=[], description=f"“{love}”\n\nSome love only shows at night.")
        self.assertIn("unsupported_context", {item["code"] for item in gate["issues"]})


class AdvisoryTagTests(unittest.TestCase):
    def test_writer_tags_are_cleaned_upload_ready(self):
        reply = {"title": "Title", "variants": ["Title"], "description": "Description.",
                 "tags": ["deep quotes,", "sad quotes, love quotes", "\"heartbreak\""], "hashtags": []}
        self.assertEqual(seo_writer._validate(reply)["tags"], ["deep quotes", "sad quotes", "love quotes", "heartbreak"])
        reply.update(tags=["Deep Quotes", "deep quotes.", "a tag that is much longer than thirty characters", "screen why"],
                     hashtags=["##quotes", "#Quotes", "shorts"])
        cleaned = seo_writer._validate(reply, short=True)
        self.assertEqual(cleaned["tags"], ["deep quotes"])
        self.assertEqual(cleaned["hashtags"], ["#quotes", "#shorts"])

    def test_brief_fragments_are_not_tag_phrases(self):
        self.assertFalse(natural_tag_phrase("screen why"))
        self.assertFalse(natural_tag_phrase("is- older get more realise how rare have"))
        self.assertFalse(natural_tag_phrase("video- there's japanese legend"))
        self.assertFalse(natural_tag_phrase("how rare have"))
        self.assertFalse(natural_tag_phrase("older get"))
        self.assertTrue(natural_tag_phrase("being valued for who you are"))
        self.assertTrue(natural_tag_phrase("no matter what"))

    def test_the_briefs_prose_never_becomes_a_final_tag(self):
        quote = "I wish memories faded as quietly as people do"
        promise = "Deep emotional resonance, relatable truth, and life perspective"
        brief = build_creator_brief(script=f"On-screen quote: '{quote}'", video_format="youtube_shorts", viewer_promise=promise)
        research = build_keyword_research(
            script=quote, creator_brief=brief, research_queries=[], entity_signals=[], youtube_results=[],
            semantic={"primary_topic": "deep emotional resonance relatable truth and life", "secondary_topics": ["fading memories"],
                      "search_intents": [], "keyword_clusters": []},
        )
        tags, evidence = select_final_tags(research, generated_tags=[], title=quote, script=quote, creator_brief=brief, is_short=True)
        self.assertNotIn("deep emotional resonance relatable truth and life", tags)
        self.assertTrue(all(len(tag) <= 30 for tag in tags))

    @patch.object(seo_writer.gemini_client, "is_available", return_value=True)
    def test_an_unrelated_tag_never_triggers_a_repair(self, _available):
        quote = "Some people are meant to be remembered, not kept"
        written = {"title": "Remembered, never kept: some people stay that way",
                   "variants": ["Remembered, never kept: some people stay that way", quote],
                   "description": f"“{quote}”\n\nSome goodbyes are a kind of keeping.",
                   "tags": ["being remembered", "crypto trading"], "hashtags": ["#shorts", "#quotes"]}
        with patch.object(seo_writer, "generate_one", side_effect=[dict(written), dict(written)]) as generate:
            packages, source = seo_writer.write_multilang_packages_with_source(
                quote, languages=["english"], creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"},
            )
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(source, "gemini")
        self.assertEqual(packages["english"]["tags"], ["being remembered"])


class LongFormTitleTests(unittest.TestCase):
    def test_a_specific_title_without_the_main_keyword_is_not_buried(self):
        script = ("Download and install OBS Studio, then copy my exact OBS settings for streaming smoothly on "
                  "YouTube: bitrate, encoder and output resolution.")
        evidence = {"selected_keywords": [{
            "keyword": "obs studio download", "classification": "core_topic", "demand_validated": True,
            "keyword_relevance_score": 90, "source_support_score": 100, "source_support": "script",
            "source_classification": "combined",
        }], "subject_terms": ["obs", "studio"]}
        scores = {}
        for title in ("My exact OBS settings for streaming smoothly on YouTube",
                      "Download and install OBS Studio for YouTube streaming"):
            package = {"title": title, "variants": [title], "description": script, "tags": ["obs studio download"], "hashtags": []}
            gate = evaluate_package_quality(package, script=script, creator_brief={"video_format": "tutorial"}, tag_evidence=evidence)
            scores[title] = gate["final_seo_quality"]["title_score"]
        specific, keyword_led = scores.values()
        self.assertGreaterEqual(specific, 90)
        self.assertLessEqual(keyword_led - specific, 6)


class UnresearchedTagTests(unittest.TestCase):
    """The AI Shorts path makes no research: the writer's tags stand on the quote alone."""

    QUOTE = "Stop explaining yourself to people who already decided to misunderstand you."

    def test_tags_built_on_the_quotes_own_words_survive_without_research(self):
        brief = build_creator_brief(script=self.QUOTE, video_format="youtube_shorts", exact_quote=self.QUOTE,
                                    visual_requirements="rain on a window at night")
        generated = ["misunderstood quotes", "being misunderstood", "stop explaining yourself", "self worth quotes",
                     "rainy window aesthetic", "shorts"]
        tags, evidence = select_final_tags({}, generated_tags=generated, title="Stop explaining yourself to them",
                                           script=self.QUOTE, creator_brief=brief, is_short=True)
        # Another form of the quote's word ("misunderstood") and the quote's own
        # words ("stop explaining yourself") are grounded; the footage and an
        # unsupported theme are not.
        for tag in ("misunderstood quotes", "being misunderstood"):
            self.assertIn(tag, tags)
        self.assertNotIn("rainy window aesthetic", tags)
        self.assertNotIn("self worth quotes", tags)
        # A run of the quote itself is still not a tag; the title carries it.
        self.assertNotIn("stop explaining yourself", tags)
        self.assertEqual(tags[-1], "shorts")


class FinalHashtagTests(unittest.TestCase):
    """The hashtags the creator pastes: #shorts, #quotes, then the quote's own feeling."""

    QUOTE = "You can miss someone and still know you're better without them"

    def generate(self, writer_output):
        from win_engine.feedback.history_store import HistoryStore
        from win_engine.generation.seo_generator import generate_seo_suggestions
        from win_engine.llm import gemini_client

        script = f"the quote is- {self.QUOTE}. the video is- rain on a window at night"
        brief = build_creator_brief(script=script, video_format="youtube_shorts")
        research = {"history_store": HistoryStore(":memory:"), "youtube_results": [], "entity_signals": [],
                    "top_opportunities": [], "upload_timing": {}, "thumbnail_intelligence": {}, "keyword_signals": []}
        with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source",
                   return_value=({"english": writer_output}, "gemini" if writer_output else "fallback")), \
             patch("win_engine.generation.strategy_engine.last_generation_diagnostics", return_value={}), \
             patch.object(gemini_client, "is_available", return_value=False):
            return generate_seo_suggestions(script, research, context={
                "language": "english", "region": "global", "creator_brief": brief,
            })

    def test_a_quote_short_package_carries_quotes_and_its_feeling_hashtag(self):
        writer_output = {
            "title": "Missing them is not a reason to go back 🥀",
            "variants": ["Missing them is not a reason to go back 🥀", "You can miss someone and still choose peace"],
            "description": f"“{self.QUOTE}.”\n\nSome goodbyes are a kind of healing.",
            "tags": ["missing someone quotes", "moving on"], "hashtags": ["#movingon"],
        }
        for output in (writer_output, None):  # Gemini's package and the local fallback
            with self.subTest(source="gemini" if output else "fallback"):
                response = self.generate(output)
                hashtags = response["hashtags"]
                self.assertEqual(hashtags[:2], ["#shorts", "#quotes"])
                self.assertEqual(len(hashtags), 3)
                self.assertTrue(response["description"].rstrip().endswith(" ".join(hashtags)))
                for lang_package in response["multilang"].values():
                    self.assertIn("#quotes", lang_package["hashtags"])


class RealSearchTagTests(unittest.TestCase):
    """Fragment rules catch phrases cut out of a creator's notes, never what viewers type."""

    REAL_SEARCHES = (
        "is iphone 16 worth it", "which iphone to buy", "text overlay capcut", "typewriter effect capcut",
        "stream overlay", "b roll footage", "on screen keyboard", "trash can", "things to do", "vitamin a",
        "premiere pro text overlay", "text overlay tutorial", "ai voiceover", "how to shoot b roll",
        "obs stream overlay", "typewriter effect", "what to do", "iphone 16 must have",
    )

    def select(self, script: str, generated: list[str], **brief_fields) -> tuple[list[str], dict]:
        brief = build_creator_brief(script=script, **brief_fields)
        research = build_keyword_research(
            script=script, creator_brief=brief, research_queries=[], entity_signals=[], youtube_results=[],
            semantic={"primary_topic": brief.get("topic"), "secondary_topics": [], "search_intents": [], "keyword_clusters": []},
        )
        return select_final_tags(research, generated_tags=generated, title=str(brief.get("topic") or ""),
                                 script=script, creator_brief=brief)

    def test_question_searches_production_words_and_short_endings_are_tag_phrases(self):
        for tag in self.REAL_SEARCHES:
            with self.subTest(tag=tag):
                self.assertTrue(natural_tag_phrase(tag))
        self.assertEqual(seo_writer.clean_tags(list(self.REAL_SEARCHES)), list(self.REAL_SEARCHES))

    def test_production_words_are_tags_only_when_the_video_is_about_them(self):
        tags, _ = self.select(
            "In this CapCut tutorial I show how to add a text overlay with a typewriter effect to your videos.",
            ["text overlay capcut", "typewriter effect capcut"], video_format="tutorial",
        )
        self.assertIn("text overlay capcut", tags)
        self.assertIn("typewriter effect capcut", tags)
        tags, _ = self.select(
            "In this OBS tutorial I set up a stream overlay and an on screen chat for YouTube live streaming.",
            ["stream overlay", "obs stream overlay"], video_format="tutorial",
        )
        self.assertIn("stream overlay", tags)
        tags, _ = self.select(
            "I review the iPhone 16 after a month. Is the iPhone 16 worth it? Which iPhone to buy if you are upgrading.",
            ["is iphone 16 worth it", "which iphone to buy"], video_format="review",
        )
        self.assertEqual({"is iphone 16 worth it", "which iphone to buy"} - set(tags), set())
        # A quote Short's notes on how it is made are not its subject.
        tags, evidence = self.select(
            "the quote is- You can miss someone and still know you're better without them. the video is- rain on "
            "a window, a typewriter reveal with a text overlay, no voiceover",
            ["text overlay", "typewriter reveal", "quote on the screen", "no voiceover"], video_format="youtube_shorts",
        )
        self.assertEqual(tags, ["shorts"])
        reasons = {row["keyword"]: row["reason"] for row in evidence["rejected_candidates"]}
        self.assertEqual(reasons.get("text overlay"), "production_note")
        self.assertEqual(reasons.get("typewriter reveal"), "production_note")

    def test_the_tag_length_cap_fits_the_format_and_the_script(self):
        long_form = ["samsung galaxy s25 ultra review", "how to install python on windows"]
        self.assertEqual(seo_writer.clean_tags(long_form), long_form)
        self.assertEqual(seo_writer.clean_tags(long_form, short=True), [])
        # Tamil writes a vowel as a sign on its consonant: 36 code points, 20 letters.
        tamil = "செட்டிநாடு சிக்கன் பிரியாணி செய்முறை"
        self.assertEqual(tag_length(tamil), 20)
        self.assertEqual(seo_writer.clean_tags([tamil], short=True), [tamil])
        # YouTube allows 500 characters of tags in all, counting the quotes it adds around a phrase.
        many = [f"python {word} tutorial for complete beginners" for word in (
            "lists", "loops", "classes", "strings", "files", "functions", "modules", "errors", "tuples",
            "sets", "dicts", "decorators",
        )]
        kept = seo_writer.clean_tags(many)
        self.assertLess(len(kept), len(many))
        self.assertLessEqual(sum(len(tag) + 2 for tag in kept) + len(kept) - 1, 500)


class QuoteTitleReviewTests(unittest.TestCase):
    SPLICE = "You don’t lose people because you stopped caring, you lose them because they stopped trying."

    def test_a_straight_apostrophe_does_not_hide_a_cut_or_a_missing_turn(self):
        quote = ("The older you get, the more you realize it’s not about who knows you the longest ... "
                 "But it’s more about who makes you seen, felt, heard and loved.")
        for title in ("But it's more about who makes you seen felt heard", "But it’s more about who makes you seen felt heard"):
            with self.subTest(title=title):
                self.assertIn("quote_title_cut", _codes(title, quote))
        self.assertIn("missing_quote_payoff", _codes("You don't lose people because you stopped caring", self.SPLICE))

    def test_a_comma_splice_after_a_negated_clause_is_the_quotes_turn(self):
        self.assertEqual(quote_punchline(self.SPLICE).rstrip("."), "you lose them because they stopped trying")
        self.assertIn("missing_quote_payoff", _codes("You don’t lose people because you stopped caring", self.SPLICE))
        reversed_title = "Because you stopped caring, you lose them because they stopped trying"
        self.assertIn("reversed_quote_meaning", _codes(reversed_title, self.SPLICE))
        title = safe_quote_title(self.SPLICE)
        self.assertEqual(title, "You lose them because they stopped trying")
        self.assertEqual(_codes(title, self.SPLICE), set())

    def test_hope_as_a_noun_and_a_question_mark_do_not_excuse_a_reversal(self):
        self.assertTrue(title_reverses_quote("Give up hope when the night is long", "Never give up hope, even when the night is long"))
        self.assertTrue(title_reverses_quote("Why I finally stopped loving you?", "I never stopped loving you"))
        # A wish states what is not so, and a question may rephrase a question.
        self.assertFalse(title_reverses_quote("Memories never fade as quietly as people do", "I wish memories faded as quietly as people do"))
        self.assertFalse(title_reverses_quote(
            "Did I deserve the bare minimum?", "A part of me will always wonder... didn’t I at least deserve the bare minimum from them?",
        ))

    def test_a_keyword_quotes_phrase_anywhere_in_the_title_fails(self):
        self.assertIn("keyword_quotes_title", _codes(
            "Heart touching sad pain quotes for missing someone", "I miss you more than words can say",
        ))

    def test_a_turn_word_that_ends_the_quote_is_not_its_turn(self):
        quote = "I asked for your time, you gave me excuses instead."
        self.assertEqual(quote_punchline(quote), "")
        self.assertEqual(_codes(quote, quote), set())

    def test_a_relative_clause_keeps_its_determiner_and_a_fragment_never_beats_a_complete_span(self):
        title = safe_quote_title("One day you will realise you were the only thing that could have saved you from yourself all along")
        self.assertEqual(title, "The only thing that could have saved you from yourself all along")
        title = safe_quote_title("Never be ashamed of your big dreams when the people around you have small ones and cannot understand it")
        self.assertEqual(title, "Never be ashamed of your big dreams")
        quote = ("Do not ever let anyone tell you that your dreams are too big, especially when the people around you "
                 "have small ones and cannot understand it")
        self.assertEqual(safe_quote_title(quote), "Do not ever let anyone tell you that your dreams are too big")
        cut = "Do not ever let anyone tell you that your dreams are too big, especially"
        gate = evaluate_package_quality(
            {"title": cut, "variants": [cut], "description": f"“{quote}”", "tags": [], "hashtags": []},
            script=quote, creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"},
        )
        self.assertEqual([row["title"] for row in gate["rejected_candidates"]], [cut])

    def test_tamil_quote_words_are_read_whole(self):
        quote = "உன்னை நினைக்காத நாளே இல்லை என் வாழ்க்கையில் ஒவ்வொரு நாளும் நீ தான்"
        self.assertEqual(_codes(quote, quote), set())
        self.assertIn("quote_title_cut", _codes("உன்னை நினைக்காத நாளே இல்லை என்", quote))


class FeelingAndHashtagReviewTests(unittest.TestCase):
    def test_a_feeling_comes_from_a_feeling_word_the_quote_does_not_negate(self):
        for quote in ("A grateful heart is a happy heart", "Follow your heart",
                      "Don't cry because it's over, smile because it happened"):
            with self.subTest(quote=quote):
                self.assertEqual(feeling_hashtag(quote), "")
                self.assertEqual(_feeling_emoji(quote), "")
        self.assertEqual(feeling_hashtag("The heart has a strange habit of missing people the mind already learned to forget."),
                         "#missingyou")
        self.assertEqual(feeling_hashtag("Even when my heart is broken I keep going"), "#heartbreak")
        self.assertEqual(_feeling_emoji("Even when my heart is broken I keep going"), "💔")

    def test_a_lowercase_coined_hashtag_counts_as_a_compound(self):
        self.assertEqual(focused_short_hashtags([], proposed=["#lettinggoofthewrongperson"]), ["#shorts"])
        for hashtag in ("#heartbreak", "#selfworth", "#missingyou", "#sadquotes", "#deepquotes", "#forgiveness", "#loneliness"):
            with self.subTest(hashtag=hashtag):
                self.assertEqual(_hashtag_length(hashtag), 1)
        # A long established label is one compound, not a phrase.
        self.assertEqual(focused_short_hashtags([], proposed=["#relationshipquotes"]), ["#shorts", "#relationshipquotes"])
        self.assertEqual(focused_short_hashtags([], proposed=["#inspirationalquotes", "#unconditionallove"]),
                         ["#shorts", "#inspirationalquotes"])
        quote = "Some people are meant to be remembered, not kept"
        gate = evaluate_package_quality(
            {"title": quote, "variants": [quote], "description": f"“{quote}”", "tags": ["shorts"],
             "hashtags": ["#shorts", "#quotes", "#lettinggoofthewrongperson"]},
            script=quote, creator_brief={"exact_quote": quote, "video_format": "youtube_shorts"},
        )
        self.assertIn("#lettinggoofthewrongperson", {item.get("hashtag") for item in gate["warnings"]})


class GatedPackageTests(unittest.TestCase):
    def test_a_tag_or_hashtag_the_final_gate_drops_does_not_ship(self):
        from win_engine.feedback.history_store import HistoryStore
        from win_engine.generation.seo_generator import generate_seo_suggestions
        from win_engine.llm import gemini_client

        script = ("In this tutorial I show how to install Python on Windows, add it to the PATH and run your "
                  "first script from the command prompt.")
        brief = build_creator_brief(script=script, video_format="tutorial")
        coined = "#InstallPythonOnWindowsToday"
        writer_output = {
            "title": "How to install Python on Windows and run your first script",
            "variants": ["How to install Python on Windows and run your first script",
                         "Install Python on Windows, add it to PATH and run a script"],
            "description": "Install Python on Windows, add it to the PATH and run your first script from the command prompt.",
            "tags": ["install python on windows"], "hashtags": ["#Python"],
        }
        research = {"history_store": HistoryStore(":memory:"), "youtube_results": [], "entity_signals": [],
                    "top_opportunities": [], "upload_timing": {}, "thumbnail_intelligence": {}, "keyword_signals": []}

        def refine(package, **_kwargs):
            # A repair may bring a tag or hashtag only the final gate judges.
            return {**package, "tags": [*package["tags"], "crypto trading"],
                    "hashtags": [*package["hashtags"], coined]}, {"attempted": False}

        with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source",
                   return_value=({"english": writer_output}, "gemini")), \
             patch("win_engine.generation.strategy_engine.last_generation_diagnostics", return_value={}), \
             patch("win_engine.generation.seo_generator.refine_package", side_effect=refine), \
             patch.object(gemini_client, "is_available", return_value=False):
            response = generate_seo_suggestions(script, research, context={
                "language": "english", "region": "global", "creator_brief": brief,
            })
        notes = response["generation_quality"]["warnings"]
        self.assertIn(coined, {item.get("hashtag") for item in notes})
        self.assertIn("crypto trading", {item.get("tag") for item in notes})
        self.assertNotIn(coined, response["hashtags"])
        self.assertNotIn(coined, response["description"])
        self.assertNotIn("crypto trading", response["tags"])
        self.assertNotIn("crypto trading", response["keyword_research"]["selected_tags"])
        self.assertTrue(response["description"].rstrip().endswith(" ".join(response["hashtags"])))


if __name__ == "__main__":
    unittest.main()
