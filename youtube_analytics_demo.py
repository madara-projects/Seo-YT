#!/usr/bin/env python3
"""
YouTube Analytics API Integration Example
This demonstrates how to integrate YouTube Analytics API for channel performance data
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class YouTubeAnalyticsClient:
    """YouTube Analytics API client for channel performance data."""

    SCOPES = [
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/yt-analytics.readonly'
    ]

    def __init__(self, client_secrets_file: str, credentials_file: str = 'youtube_credentials.json'):
        self.client_secrets_file = client_secrets_file
        self.credentials_file = credentials_file
        self.credentials = None
        self.youtube_analytics = None

    def authenticate(self) -> bool:
        """Authenticate with YouTube Analytics API using OAuth 2.0."""
        try:
            # Load existing credentials if available
            if os.path.exists(self.credentials_file):
                self.credentials = Credentials.from_authorized_user_file(self.credentials_file, self.SCOPES)

            # Refresh or re-authenticate if needed
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secrets_file, self.SCOPES
                    )
                    self.credentials = flow.run_local_server(port=8080)

                # Save credentials for future use
                with open(self.credentials_file, 'w') as token:
                    token.write(self.credentials.to_json())

            # Build the YouTube Analytics API service
            self.youtube_analytics = build('youtubeAnalytics', 'v2', credentials=self.credentials)
            return True

        except Exception as e:
            logger.error(f"YouTube Analytics authentication failed: {e}")
            return False

    def get_channel_basic_stats(self, days: int = 30) -> Optional[Dict[str, Any]]:
        """Get basic channel statistics for the last N days."""
        if not self.youtube_analytics:
            return None

        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            response = self.youtube_analytics.reports().query(
                ids='channel==MINE',
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics='views,estimatedMinutesWatched,subscribersGained,subscribersLost,likes,dislikes,shares,comments',
                dimensions='day',
                sort='day'
            ).execute()

            return self._process_analytics_response(response)

        except HttpError as e:
            logger.error(f"YouTube Analytics API error: {e}")
            return None

    def get_video_performance(self, video_id: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """Get detailed performance metrics for a specific video."""
        if not self.youtube_analytics:
            return None

        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            response = self.youtube_analytics.reports().query(
                ids=f'channel==MINE',
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,dislikes,shares,comments',
                dimensions='video',
                filters=f'video=={video_id}',
                sort='views'
            ).execute()

            return self._process_analytics_response(response)

        except HttpError as e:
            logger.error(f"YouTube Analytics API error for video {video_id}: {e}")
            return None

    def get_demographics_data(self, days: int = 30) -> Optional[Dict[str, Any]]:
        """Get audience demographics (age, gender, geography)."""
        if not self.youtube_analytics:
            return None

        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            response = self.youtube_analytics.reports().query(
                ids='channel==MINE',
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics='viewerPercentage',
                dimensions='ageGroup,gender,country',
                sort='viewerPercentage'
            ).execute()

            return self._process_analytics_response(response)

        except HttpError as e:
            logger.error(f"YouTube Analytics demographics API error: {e}")
            return None

    def get_traffic_sources(self, days: int = 30) -> Optional[Dict[str, Any]]:
        """Get traffic source breakdown."""
        if not self.youtube_analytics:
            return None

        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            response = self.youtube_analytics.reports().query(
                ids='channel==MINE',
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics='views,estimatedMinutesWatched',
                dimensions='insightTrafficSourceType',
                sort='views'
            ).execute()

            return self._process_analytics_response(response)

        except HttpError as e:
            logger.error(f"YouTube Analytics traffic sources API error: {e}")
            return None

    def _process_analytics_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Process and format analytics API response."""
        try:
            headers = response.get('columnHeaders', [])
            rows = response.get('rows', [])

            # Convert to more readable format
            processed_data = []
            for row in rows:
                row_data = {}
                for i, value in enumerate(row):
                    if i < len(headers):
                        header = headers[i]['name']
                        row_data[header] = value
                processed_data.append(row_data)

            return {
                'headers': [h['name'] for h in headers],
                'data': processed_data,
                'total_results': len(processed_data)
            }

        except Exception as e:
            logger.error(f"Error processing analytics response: {e}")
            return {}

# Example usage
def demo_youtube_analytics():
    """Demonstrate YouTube Analytics API integration."""
    # This would require:
    # 1. Google Cloud Console project with YouTube Analytics API enabled
    # 2. OAuth 2.0 client credentials downloaded as client_secrets.json
    # 3. User authentication flow

    analytics_client = YouTubeAnalyticsClient('client_secrets.json')

    if analytics_client.authenticate():
        print("✅ Successfully authenticated with YouTube Analytics API")

        # Get channel stats
        stats = analytics_client.get_channel_basic_stats(days=7)
        if stats:
            print(f"📊 Channel has {len(stats['data'])} days of analytics data")

        # Get demographics
        demographics = analytics_client.get_demographics_data(days=30)
        if demographics:
            print(f"🌍 Demographics data available for {len(demographics['data'])} segments")

        # Get traffic sources
        traffic = analytics_client.get_traffic_sources(days=30)
        if traffic:
            print(f"🚦 Traffic source data available for {len(traffic['data'])} sources")

    else:
        print("❌ Authentication failed - check credentials and API setup")

if __name__ == '__main__':
    demo_youtube_analytics()