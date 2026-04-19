# Test Configuration and Fixtures
import pytest
import sys
import os
from unittest.mock import Mock, patch
from typing import Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from win_engine.core.config import Settings, get_settings


@pytest.fixture
def sample_script() -> str:
    """Sample YouTube script for testing."""
    return """
    Welcome to this comprehensive guide on how to grow your YouTube channel from 0 to 10,000 subscribers.
    Today I'm going to share the exact strategies that helped me reach 10k subscribers in just 6 months.
    We'll cover thumbnail optimization, title creation, SEO techniques, and content planning.
    First, let's talk about the importance of eye-catching thumbnails.
    Your thumbnail is the first thing viewers see, and it can make or break your click-through rate.
    I'll show you how to design thumbnails that get 50% more clicks.
    """


@pytest.fixture
def mock_youtube_response() -> Dict[str, Any]:
    """Mock YouTube API response for testing."""
    return {
        "items": [
            {
                "id": {"videoId": "test123"},
                "snippet": {
                    "title": "Test Video Title",
                    "description": "Test video description",
                    "channelTitle": "Test Channel",
                    "publishedAt": "2024-01-01T00:00:00Z",
                    "thumbnails": {"default": {"url": "https://example.com/thumb.jpg"}}
                }
            }
        ]
    }


@pytest.fixture
def test_settings() -> Settings:
    """Test settings configuration."""
    return Settings(
        app_name="Test App",
        app_environment="testing",
        youtube_api_keys="test_key_1,test_key_2",
        database_path=":memory:",  # Use in-memory SQLite for tests
        cache_ttl_trending_seconds=60,
        cache_ttl_evergreen_seconds=300,
    )


@pytest.fixture(autouse=True)
def mock_settings(test_settings):
    """Automatically mock settings for all tests."""
    with patch('win_engine.core.config.get_settings', return_value=test_settings):
        yield


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for API testing."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {"items": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_spacy_nlp():
    """Mock spaCy NLP for testing."""
    with patch('win_engine.analysis.nlp_titlegen.nlp') as mock_nlp:
        # Create mock tokens
        mock_token = Mock()
        mock_token.lemma_ = "subscriber"
        mock_token.pos_ = "NOUN"
        mock_token.is_stop = False
        mock_token.text = "subscriber"

        # Create mock noun chunks
        mock_chunk = Mock()
        mock_chunk.text = "test chunk"

        # Create mock doc with proper iteration
        mock_doc = Mock()
        mock_doc.__iter__ = Mock(return_value=iter([mock_token]))
        mock_doc.noun_chunks = [mock_chunk]

        mock_nlp.return_value = mock_doc
        yield mock_nlp