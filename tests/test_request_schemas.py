"""Request models refuse input that would spend quota on nothing."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from win_engine.api.app import create_app
from win_engine.core.schemas import AnalyzeRequest, CreateIdeaRequest, DemandResearchRequest, UpdateIdeaRequest


class ContentFreeInputTests(unittest.TestCase):
    def test_a_script_needs_at_least_one_word(self):
        for script in ("🔥🔥🔥", "!!! ???", "❤️ 💔"):
            with self.subTest(script=script), self.assertRaises(ValidationError):
                AnalyzeRequest(script=script)
        # Tamil vowel signs and digits are word characters.
        self.assertEqual(AnalyzeRequest(script="பிரியாணி 🔥").script, "பிரியாணி 🔥")
        self.assertEqual(AnalyzeRequest(script="2024").script, "2024")

    def test_a_topic_needs_at_least_one_word(self):
        for model in (CreateIdeaRequest, DemandResearchRequest):
            with self.subTest(model=model.__name__), self.assertRaises(ValidationError):
                model(topic="🔥🔥")
        with self.assertRaises(ValidationError):
            UpdateIdeaRequest(topic="✨")
        self.assertIsNone(UpdateIdeaRequest(notes="Shoot at dusk").topic)

    def test_an_emoji_only_script_is_refused_before_any_research(self):
        client = TestClient(create_app())
        with patch("win_engine.api.routes.generate_seo_suggestions") as generate:
            response = client.post("/analyze", json={"script": "🔥🔥🔥"})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["message"], "script: Enter at least one word.")
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
