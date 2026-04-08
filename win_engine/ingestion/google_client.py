from __future__ import annotations

import logging
from typing import Any, List

import requests


logger = logging.getLogger(__name__)


class GoogleSearchClient:
    """Google Custom Search JSON API client."""

    _SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str | None, cse_id: str | None, timeout_seconds: int) -> None:
        self._api_key = api_key
        self._cse_id = cse_id
        self._timeout = timeout_seconds

    def search(
        self,
        query: str,
        max_results: int = 5,
        raise_on_error: bool = False,
    ) -> List[dict[str, Any]]:
        if not self._api_key or not self._cse_id:
            logger.warning("Google search API not configured; returning empty results")
            return []

        params = {
            "key": self._api_key,
            "cx": self._cse_id,
            "q": query,
            "num": max_results,
        }

        try:
            response = requests.get(self._SEARCH_URL, params=params, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.exception("Google search failed: %s", exc)
            if raise_on_error:
                raise
            return []

        items = payload.get("items", [])
        results: List[dict[str, Any]] = []

        for item in items:
            results.append(
                {
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                }
            )

        return results
