"""Search suggestions keep non-English words whole and ask in the right locale."""

import unittest
from unittest.mock import MagicMock, patch

from win_engine.ingestion.search_suggest import SearchSuggestClient, normalize_phrase


class NormalizePhraseTests(unittest.TestCase):
    def test_vowel_signs_do_not_split_words(self):
        # Devanagari vowel signs are combining marks; they used to become spaces.
        self.assertEqual(normalize_phrase("हिन्दी गाना!"), "हिन्दी गाना")
        self.assertEqual(normalize_phrase("செட்டிநாடு  பிரியாணி"), "செட்டிநாடு பிரியாணி")

    def test_single_characters_and_apostrophes_survive(self):
        self.assertEqual(normalize_phrase("GTA 5 Map’s Secrets"), "gta 5 map's secrets")

    def test_emoji_marks_and_joiners_are_not_kept(self):
        # U+FE0F after an emoji is a combining mark; kept, it glued itself to the next word.
        self.assertEqual(normalize_phrase("❤️love quotes"), "love quotes")
        # A family emoji is joined by U+200D; without the emoji the joiner is stray.
        self.assertEqual(normalize_phrase("👨‍👩‍👧 vlog"), "vlog")


class LocaleTests(unittest.TestCase):
    def fetch_params(self, **locale):
        with patch("win_engine.ingestion.search_suggest.httpx.get") as get:
            get.return_value = MagicMock(status_code=200, content=b'["x",["x y"]]')
            SearchSuggestClient(enabled=True, timeout_seconds=1, max_queries=1).fetch(["x"], **locale)
        return get.call_args.kwargs["params"]

    def test_language_and_region_reach_the_request(self):
        params = self.fetch_params(language="tamil", region="tamil nadu")
        self.assertEqual((params["hl"], params["gl"]), ("ta", "IN"))
        params = self.fetch_params(language="hindi", region="sri lanka")
        self.assertEqual((params["hl"], params["gl"]), ("hi", "LK"))

    def test_tanglish_is_typed_in_latin_letters(self):
        self.assertEqual(self.fetch_params(language="tanglish", region="global")["hl"], "en")

    def test_a_region_spanning_countries_sends_no_country(self):
        self.assertNotIn("gl", self.fetch_params(language="english", region="gulf"))


if __name__ == "__main__":
    unittest.main()
