import json
import urllib.request
from pathlib import Path

quote = "Sometimes the pieces of our heart are easier to hide than to mend."

script_content = (
    "Format: YouTube Short, 12 seconds, English.\n"
    "Visual: Cinematic moody evening rain on autumn leaves with soft amber bokeh city lights, gentle melancholic lofi ambient music.\n"
    f'Exact on-screen quote: "{quote}"\n'
    "Voice-over: none. Music: soft melancholic piano and lofi rain ambient.\n"
    "Mood: silent heartbreak, emotional vulnerability, healing, and quiet reflection.\n"
    "Audience: people carrying silent pain and hiding heartbreak rather than confronting it.\n"
    "Do not invent facts or change the quote meaning."
)

payload = {
    "script": script_content,
    "video_language": "english",
    "language": "english",
    "region": "global",
    "audience_type": "general",
    "target_audience": "people carrying silent pain and hiding heartbreak rather than confronting it",
    "viewer_promise": "quiet comfort, emotional validation, and gentle encouragement to heal",
    "unique_angle": "the silent exhaustion of pretending you are okay and hiding broken pieces",
    "proof": "relatable emotional vulnerability and moody cinematic atmosphere",
    "video_format": "Short",
    "title_style": "balanced",
    "thumbnail_idea": "close-up of rain on autumn glass with soft glowing bokeh and on-screen quote text",
    "duration_seconds": 12.0,
    "exact_quote": quote,
    "on_screen_text": quote,
    "voice_over": "none",
    "visual_requirements": "Cinematic moody evening rain on autumn leaves with soft amber bokeh city lights, gentle melancholic lofi ambient music.",
    "factual_claims": "None",
    "claim_restrictions": "Do not invent backstory, names, or false claims.",
    "creator_intent": "poetic quote video offering gentle reflection on hiding pain vs healing",
    "content_constraints": "preserve exact quote, no voice-over, no invented claims"
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/analyze",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

print("Sending request to http://127.0.0.1:8000/analyze for quote...")
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        output_path = Path("runtime/artifacts/manual/pieces_quote_response.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print("SUCCESS: HTTP", resp.status)
except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code, e.read().decode("utf-8", errors="replace"))
except Exception as e:
    print("ERROR:", e)
