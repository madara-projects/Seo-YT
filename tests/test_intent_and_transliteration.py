"""Intent labels and phonetic matching that simplified code paths must keep."""

import unittest

from win_engine.analysis import transliteration
from win_engine.analysis.intent_classifier import classify_intent


class IntentAndTransliterationTests(unittest.TestCase):
    def test_intent_labels_are_unchanged(self):
        self.assertEqual(classify_intent("How to set up a tripod"), "SEARCH")
        self.assertEqual(classify_intent("I tried waking up at 5am for 30 days"), "BROWSE")
        self.assertEqual(classify_intent("The shocking secret nobody talks about"), "SUGGESTED")
        self.assertEqual(classify_intent("A quiet evening by the sea"), "SUGGESTED")

    def test_tamil_and_latin_spellings_share_a_phonetic_key(self):
        self.assertEqual(transliteration.phonetic_key("biryani"), transliteration.phonetic_key("பிரியாணி"))


if __name__ == "__main__":
    unittest.main()
