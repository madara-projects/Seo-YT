from __future__ import annotations

from typing import Optional, Tuple

from flask import Request, jsonify


def get_script_or_error(request: Request) -> Tuple[Optional[str], Optional[tuple]]:
    """Validate input JSON and return (script, error_response)."""

    data = request.get_json(silent=True)
    if not data or "script" not in data:
        return None, (jsonify({"error": "Missing required field: script"}), 400)

    script = str(data.get("script", "")).strip()
    if not script:
        return None, (jsonify({"error": "Field 'script' cannot be empty"}), 400)

    return script, None
