"""One region table serves request validation and YouTube's regionCode."""
from __future__ import annotations

import unittest

from win_engine.core.regions import REGION_ALIASES
from win_engine.core.schemas import normalize_region
from win_engine.ingestion.youtube_client import youtube_region_code


class RegionTableTests(unittest.TestCase):
    def test_request_regions_normalize_to_the_names_research_matches(self):
        expected = {
            "in": "india", "IND": "india", "India (IN)": "india", "tn": "tamil nadu", "lk": "sri lanka",
            "usa": "us", "United States": "us", "united states (us)": "us", "gb": "uk", "united kingdom": "uk",
            "india": "india", " Global ": "global", "gulf": "gulf",
        }
        for value, name in expected.items():
            self.assertEqual(normalize_region(value), name, value)

    def test_youtube_region_codes(self):
        expected = {
            "india": "IN", "in": "IN", "tamil nadu": "IN", "sri lanka": "LK", "lk": "LK", "us": "US", "USA": "US",
            "united states": "US", "uk": "GB", "gb": "GB", "united kingdom": "GB",
            "gulf": None, "global": None, "": None, None: None,
        }
        for region, code in expected.items():
            self.assertEqual(youtube_region_code(region), code, region)

    def test_an_alias_gets_the_code_of_the_region_it_names(self):
        for alias, name in REGION_ALIASES.items():
            self.assertEqual(normalize_region(alias), name)
            self.assertEqual(youtube_region_code(alias), youtube_region_code(name), alias)


if __name__ == "__main__":
    unittest.main()
