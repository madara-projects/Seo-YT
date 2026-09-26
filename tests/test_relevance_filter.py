"""The research relevance filter reads every script and short words."""

import unittest

from win_engine.ingestion.research_service import ResearchService

TAMIL_QUERY = "செட்டிநாடு சிக்கன் பிரியாணி"


def _kept(rows, creator_brief=None):
    return [row["video_id"] for row in ResearchService._filter_relevant_results(rows, creator_brief)]


class ScriptTests(unittest.TestCase):
    def test_tamil_query_keeps_tamil_and_latin_spellings_of_its_words(self):
        # Every result of a Tamil query used to be dropped: 102 units for nothing.
        rows = [
            {"video_id": "tamil", "title": "செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி", "research_query": TAMIL_QUERY},
            {"video_id": "latin", "title": "Chettinad Chicken Biryani Recipe in Tamil", "research_query": TAMIL_QUERY},
            {"video_id": "other", "title": "Mutton curry in 10 minutes", "research_query": TAMIL_QUERY},
        ]

        self.assertEqual(_kept(rows), ["tamil", "latin"])

    def test_hindi_words_stay_whole(self):
        rows = [{"video_id": "hindi", "title": "हिन्दी गाना 2024", "research_query": "हिन्दी गाना"}]

        (row,) = ResearchService._filter_relevant_results(rows)

        self.assertEqual(row["research_relevance_terms"], ["गाना", "हिन्दी"])

    def test_sound_alike_bridge_is_only_between_scripts(self):
        # "chicken" and "skin" share a consonant skeleton; within English that is a coincidence.
        rows = [{"video_id": "skin", "title": "Skin recipe", "research_query": "chicken recipe"}]

        self.assertEqual(_kept(rows), [])


class ShortWordTests(unittest.TestCase):
    def test_three_character_words_and_model_codes_are_query_terms(self):
        rows = [
            {"video_id": "god", "title": "Words about God", "research_query": "god quotes"},
            {"video_id": "war", "title": "The Art of War explained", "research_query": "art of war"},
            {"video_id": "ps5", "title": "PS5 vs Xbox", "research_query": "ps5"},
        ]

        self.assertEqual(_kept(rows), ["god", "war", "ps5"])

    def test_common_three_letter_words_are_not_evidence(self):
        self.assertEqual(ResearchService._query_terms("why you are not alone"), {"alone"})
        self.assertEqual(ResearchService._query_terms("quotes shorts"), set())

    def test_curly_and_straight_apostrophes_are_one_word(self):
        rows = [{"video_id": "love", "title": "A mother's love", "research_query": "mother’s love"}]

        self.assertEqual(_kept(rows), ["love"])


if __name__ == "__main__":
    unittest.main()
