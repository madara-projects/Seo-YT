"""Unit tests for title generation functionality."""
import pytest
from unittest.mock import patch

from win_engine.analysis.nlp_titlegen import (
    generate_dynamic_title,
    generate_dynamic_description,
    generate_title_variants,
    extract_main_entities
)


class TestTitleGeneration:
    """Test cases for title generation functions."""

    def test_generate_dynamic_title_basic(self, sample_script):
        """Test basic title generation."""
        title = generate_dynamic_title(sample_script)

        assert isinstance(title, str)
        assert len(title) > 0
        assert len(title) < 100  # YouTube title limit

    def test_generate_dynamic_title_with_entities(self, sample_script, mock_spacy_nlp):
        """Test title generation with entity extraction."""
        # Mock the NLP processing
        mock_token = mock_spacy_nlp.return_value[0]
        mock_token.lemma_ = "subscriber"
        mock_token.pos_ = "NOUN"
        mock_token.is_stop = False

        title = generate_dynamic_title(sample_script)

        assert isinstance(title, str)
        assert "subscriber" in title.lower() or "channel" in title.lower()

    def test_generate_title_variants(self, sample_script):
        """Test generation of multiple title variants."""
        variants = generate_title_variants(sample_script, count=3)

        assert isinstance(variants, list)
        assert len(variants) == 3

        for variant in variants:
            assert "title" in variant
            assert "score" in variant
            assert isinstance(variant["title"], str)
            assert isinstance(variant["score"], (int, float))

    def test_generate_dynamic_description(self, sample_script):
        """Test description generation."""
        description = generate_dynamic_description(sample_script)

        assert isinstance(description, str)
        assert len(description) > 100  # Should be substantial
        assert "timestam" in description.lower()  # Should include timestamps
        assert "#" in description  # Should include hashtags

    def test_extract_main_entities(self, sample_script, mock_spacy_nlp):
        """Test entity extraction."""
        entities = extract_main_entities(sample_script)

        assert isinstance(entities, dict)
        # Should contain expected keys
        expected_keys = ["topics", "actions", "entities"]
        for key in expected_keys:
            assert key in entities

    @pytest.mark.parametrize("script_input,expected_contains", [
        ("how to grow youtube channel", ["grow", "youtube", "channel"]),
        ("tips for video thumbnails", ["tips", "video", "thumbnail"]),
        ("best seo strategies", ["strategy", "seo", "best"]),
    ])
    def test_title_adaptation_to_content(self, script_input, expected_contains):
        """Test that titles are relevant to input content."""
        title = generate_dynamic_title(script_input)

        # Title should contain at least one of the expected words
        title_lower = title.lower()
        assert any(expected.lower() in title_lower for expected in expected_contains), \
            f"Title '{title}' should contain one of {expected_contains}"

    def test_title_length_constraints(self, sample_script):
        """Test that generated titles meet YouTube constraints."""
        title = generate_dynamic_title(sample_script)

        # YouTube title limit is 100 characters
        assert len(title) <= 100

        # Should not be too short
        assert len(title) >= 10

    def test_description_comprehensive(self, sample_script):
        """Test that descriptions are comprehensive."""
        description = generate_dynamic_description(sample_script)

        # Should contain essential elements
        essential_elements = [
            "learn",  # Value proposition
            "⏱️",     # Timestamps
            "#",      # Hashtags
            "subscribe"  # CTA
        ]

        description_lower = description.lower()
        for element in essential_elements:
            assert element.lower() in description_lower