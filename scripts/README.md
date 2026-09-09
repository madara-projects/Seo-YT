# Utility scripts

Run these commands from the repository root.

- `python scripts/quote_quality_probe.py "Your quote"` sends quotes to the running local API and prints compact quality evidence.
- `python scripts/dev/generate_quote_request.py` runs a manual quote request and writes its response under `runtime/artifacts/manual/`.
- `python scripts/dev/probe_pieces_quote.py` runs the alternate quote probe and writes its response under `runtime/artifacts/manual/`.
- `python scripts/dev/evaluate_quote_package.py` exercises package-quality logic with controlled local inputs.

Files under `dev/` are diagnostic helpers, not production entry points. Generated responses belong in `runtime/artifacts/` and are intentionally excluded from Git.
