"""Unit tests for YouTube API client."""
import pytest
from unittest.mock import Mock, patch

from win_engine.ingestion.youtube_client import YouTubeClient


class TestYouTubeClient:
    """Test cases for YouTube API client."""

    @pytest.fixture
    def youtube_client(self, test_settings):
        """Create YouTube client for testing."""
        return YouTubeClient(
            api_keys=test_settings.youtube_api_key_pool,
            timeout_seconds=10
        )

    def test_client_initialization(self, test_settings):
        """Test client initialization."""
        client = YouTubeClient(
            api_keys=["key1", "key2"],
            timeout_seconds=30
        )

        assert client._api_keys == ["key1", "key2"]
        assert client._timeout == 30
        assert client._active_key_index == 0

    def test_search_videos_success(self, youtube_client, mock_requests_get, mock_youtube_response):
        """Test successful video search."""
        mock_requests_get.return_value.json.return_value = mock_youtube_response

        results = youtube_client.search_videos("test query", max_results=1)

        assert len(results) == 1
        assert results[0]["video_id"] == "test123"
        assert results[0]["title"] == "Test Video Title"
        assert results[0]["channel_title"] == "Test Channel"

    def test_search_videos_no_api_key(self):
        """Test search without API key."""
        client = YouTubeClient(api_keys=[], timeout_seconds=10)

        results = client.search_videos("test query")

        assert results == []
        assert client._last_warning == "YouTube API key is missing."

    def test_search_videos_api_error(self, youtube_client, mock_requests_get):
        """Test handling of API errors."""
        mock_requests_get.return_value.raise_for_status.side_effect = Exception("API Error")

        results = youtube_client.search_videos("test query", raise_on_error=False)

        assert results == []

    def test_quota_window_refresh(self, youtube_client):
        """Test quota window refresh logic."""
        from datetime import datetime, timezone

        # Set last reset to yesterday
        yesterday = datetime.now(timezone.utc).date().replace(day=datetime.now(timezone.utc).day - 1)
        youtube_client._last_reset_date = yesterday

        # Call method that checks quota window
        youtube_client.search_videos("test", max_results=0)

        # Should have refreshed the date
        assert youtube_client._last_reset_date == datetime.now(timezone.utc).date()

    def test_api_key_rotation(self, youtube_client, mock_requests_get):
        """Test API key rotation on quota exceeded."""
        # Mock quota exceeded response
        mock_response = Mock()
        mock_response.json.return_value = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
        mock_response.raise_for_status.side_effect = Exception("Quota exceeded")
        mock_requests_get.return_value = mock_response

        # First call should try first key
        youtube_client.search_videos("test", raise_on_error=False)

        # Should have rotated to next key
        assert youtube_client._active_key_index == 1

    @pytest.mark.parametrize("max_results", [1, 5, 10])
    def test_search_max_results(self, youtube_client, mock_requests_get, mock_youtube_response, max_results):
        """Test max_results parameter."""
        mock_youtube_response["items"] = mock_youtube_response["items"] * max_results
        mock_requests_get.return_value.json.return_value = mock_youtube_response

        results = youtube_client.search_videos("test", max_results=max_results)

        assert len(results) <= max_results

    def test_video_stats_fetching(self, youtube_client, mock_requests_get):
        """Test video statistics fetching."""
        # Mock videos response
        videos_response = {
            "items": [{
                "id": "test123",
                "statistics": {"viewCount": "1000", "likeCount": "50"},
                "contentDetails": {"duration": "PT5M30S"}
            }]
        }
        mock_requests_get.return_value.json.return_value = videos_response

        # This would be called internally by search_videos
        stats = youtube_client._fetch_video_stats(["test123"])

        assert "test123" in stats
        assert stats["test123"]["viewCount"] == "1000"
        assert stats["test123"]["duration"] == "PT5M30S"