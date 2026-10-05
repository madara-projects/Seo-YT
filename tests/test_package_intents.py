"""Package labels ("Search", "Browse") follow the title, not its position in the writer's list.

The writer stage labelled its variants Search, Browse and Existing audience by
index, so a how-to in second place was "Browse" and a question in first place
"Search / new viewers". A Short is found in the feed, so it carries no
search-or-browse label at all.
"""

import unittest

from win_engine.analysis.package_builder import build_title_thumbnail_packages, package_intent_for_title

TUTORIAL = {"content": "A practical CSV parsing tutorial for Python automation.", "video_format": "tutorial"}
QUOTE = "Stop explaining yourself to people who already decided to misunderstand you"
SHORT = {"content": QUOTE, "exact_quote": QUOTE, "on_screen_text": QUOTE, "video_format": "youtube_shorts",
         "visual_requirements": "rainy road with vehicles"}


class LongFormLabelTests(unittest.TestCase):
    def test_labels_come_from_what_the_title_does(self):
        cases = {
            "How to Parse CSV Files Without Breaking Rows": "Search",
            "Python CSV Parsing Tutorial for Automation": "Search",
            "Pandas vs the csv Module for Large Files": "Search",
            "What Is a CSV Delimiter? Explained Simply": "Search",
            "Why CSV Rows Break in Python Automation": "Browse",
            "Is Your CSV Parser Silently Dropping Rows?": "Browse",
            "The CSV Bug Hiding in Your Automation": "Browse",
            "I Finally Fixed My Most Annoying CSV Bug": "Browse",
            "A Safer Way to Parse CSV Files in Python": "Search and browse",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(package_intent_for_title(title, TUTORIAL), expected)

    def test_a_title_that_opens_with_the_videos_subject_is_search(self):
        # A plain keyword title leads with the words viewers type: its mechanism
        # is search even without a "how to". A benefit opening only hints at it.
        brief = {"topic": "local chennai street food walking tour through small", "video_format": "talking_head"}
        self.assertEqual(
            package_intent_for_title("Local Chennai Street Food Walking Tour Through Small Evening", brief), "Search",
        )
        self.assertEqual(package_intent_for_title("A Safer Way to Find Chennai Street Food", brief), "Search and browse")
        self.assertEqual(package_intent_for_title("Why Chennai Street Food Tastes Better at Night", brief), "Browse")

    def test_the_positional_labels_are_ignored(self):
        packages = build_title_thumbnail_packages(
            [{"title": "Why CSV Rows Break in Python Automation", "package_intent": "Search", "discovery_surface": "Search"},
             {"title": "How to Parse CSV Files Without Breaking Rows", "package_intent": "Browse", "discovery_surface": "Browse"},
             {"title": "I Finally Fixed My Most Annoying CSV Bug", "package_intent": "Existing audience",
              "discovery_surface": "Existing audience"}],
            TUTORIAL, validated=True,
        )
        self.assertEqual([item["package_intent"] for item in packages], ["Browse", "Search", "Browse"])
        self.assertEqual([item["discovery_surface"] for item in packages], ["Browse", "Search", "Browse"])
        self.assertEqual([item["best_for"] for item in packages], [
            "Browse / home and suggested viewers", "Search / new viewers", "Browse / home and suggested viewers",
        ])
        self.assertIn("words viewers type", packages[1]["why_click"])
        self.assertNotIn("words viewers type", packages[0]["why_click"])
        self.assertNotIn("Existing audience", str(packages))


class ShortsLabelTests(unittest.TestCase):
    TITLES = ["Stop explaining yourself to people who refuse to listen #shorts",
              "Why do people decide to misunderstand you? #shorts"]

    def test_a_short_carries_no_search_or_browse_label(self):
        packages = build_title_thumbnail_packages(
            [{"title": self.TITLES[0], "package_intent": "Search"}, {"title": self.TITLES[1], "package_intent": "Browse"}],
            SHORT, validated=True,
        )
        self.assertEqual(len(packages), 2)
        for item in packages:
            with self.subTest(title=item["title"]):
                self.assertEqual(item["package_intent"], "Shorts feed")
                self.assertEqual(item["discovery_surface"], "Shorts feed")
                self.assertEqual(item["best_for"], "Shorts feed / relatable viewers")
                self.assertNotIn("search", item["why_click"].casefold())
                self.assertIn("feed", item["why_click"].casefold())
        self.assertIn("background (rainy road with vehicles)", packages[0]["why_click"])

    def test_a_title_tagged_shorts_is_a_short_whatever_the_brief_says(self):
        self.assertEqual(package_intent_for_title(self.TITLES[0], {}), "Shorts feed")
        self.assertEqual(package_intent_for_title("Stop explaining yourself to people who refuse to listen", {}),
                         "Search and browse")


class ThumbnailTextTests(unittest.TestCase):
    """Thumbnail text is a complete, readable phrase, and each option has its own."""

    def packages(self, titles, focus=None):
        variants = [{"title": title} for title in titles]
        return build_title_thumbnail_packages(variants, SHORT, validated=True, focus_phrases=focus or [])

    def test_a_window_with_filler_inside_never_beats_a_clean_phrase(self):
        # Live: "YOURSELF WHEN THEY ALREADY" from this title, with no tag to anchor on.
        [package] = self.packages(["Stop explaining yourself when they already misunderstand you"])
        text = package["thumbnail_text"]
        self.assertNotIn(" WHEN ", f" {text} ")
        self.assertFalse(text.endswith(("ALREADY", "THEY", "WHEN")))
        self.assertEqual(text, "STOP EXPLAINING YOURSELF")

    def test_thumbnail_text_is_a_run_of_the_titles_own_words(self):
        # "TALKING PEOPLE" came from "talking to people": a word dropped from the
        # middle glues a phrase nobody wrote.
        titles = [
            "The exhaustion of talking to people who refuse to understand",
            "Stop explaining yourself to people who decided to misunderstand you",
            "When you finally stop wasting energy explaining yourself",
        ]
        for package in self.packages(titles):
            words = " ".join(w for w in package["title"].upper().replace(",", "").split() if w not in {"THE", "A", "AN"})
            with self.subTest(title=package["title"]):
                self.assertIn(f" {package['thumbnail_text']} ", f" {words} ")

    def test_each_option_gets_its_own_thumbnail_text(self):
        titles = [
            "Sad love quotes for the nights you overthink",
            "Sad love quotes that say what you never could",
            "Sad love quotes for anyone still waiting",
        ]
        texts = [package["thumbnail_text"] for package in self.packages(titles, focus=["sad love quotes"])]
        self.assertEqual(len(texts), 3)
        self.assertEqual(len(set(texts)), 3, texts)
        self.assertEqual(texts[0], "SAD LOVE QUOTES")
        for text in texts:
            self.assertTrue(2 <= len(text.split()) <= 5, text)


if __name__ == "__main__":
    unittest.main()
