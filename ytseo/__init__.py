"""Application package for the YouTube SEO Analyzer backend."""

from flask import Flask, jsonify

from ytseo.routes import register_routes


def create_app() -> Flask:
    """Application factory for clean structure and easy testing."""
    app = Flask(__name__)

    register_routes(app)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(_error):
        return jsonify({"error": "Internal server error"}), 500

    return app
