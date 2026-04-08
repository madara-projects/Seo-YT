from flask import Flask, jsonify, request

from ytseo.services.seo_service import generate_seo_suggestions
from ytseo.utils.validation import get_script_or_error


def register_routes(app: Flask) -> None:
    """Register API routes on the Flask app."""

    @app.get("/health")
    def health_check():
        return jsonify({"status": "ok"}), 200

    @app.post("/analyze")
    def analyze_script():
        script, error_response = get_script_or_error(request)
        if error_response is not None:
            return error_response

        result = generate_seo_suggestions(script)
        return jsonify(result), 200
