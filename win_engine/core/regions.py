"""Creator-facing regions: the one table request validation and YouTube search share."""

from __future__ import annotations

# Each region's name (what the research engines match on), its ISO 3166-1 code
# for YouTube's regionCode, and the other spellings the classic dashboard and
# API callers send ("in" used to fall through to global). "gulf" spans several
# countries, so like "global" it gets no code and no regional bias.
_REGIONS = {
    "india": ("IN", ("in", "ind", "india (in)")),
    "tamil nadu": ("IN", ("tn",)),
    "sri lanka": ("LK", ("lk",)),
    "us": ("US", ("usa", "united states", "united states (us)")),
    "uk": ("GB", ("gb", "united kingdom")),
}

# Spelling → region name, for requests.
REGION_ALIASES = {alias: name for name, (_, aliases) in _REGIONS.items() for alias in aliases}
# Region name or spelling → ISO 3166-1 code.
REGION_CODES = {key: code for name, (code, aliases) in _REGIONS.items() for key in (name, *aliases)}
