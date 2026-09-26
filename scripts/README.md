# Utility scripts

Run these commands from the repository root.

- `python scripts/quote_quality_probe.py "Your quote" ["Another quote" ...]` sends each quote to the running local API and prints compact quality evidence.

Each quote is a full `/analyze` request, so it spends YouTube and Gemini quota. For checks that must not, use the tests (`python -m pytest tests`), which never reach the network.
