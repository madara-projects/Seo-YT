import json
import urllib.request
from pathlib import Path

script_content = (
    "Format: YouTube Short, 12 seconds, English.\n"
    "Visual: Cinematic moody rainy city window at dusk, raindrops slowly sliding down the glass with soft blurred streetlights and distant taillights in the background.\n"
    "Exact on-screen quote: \"Hope can be cruel when it keeps you waiting for a person who will never return.\"\n"
    "Voice-over: none. Mood: melancholic reflection, acceptance, heartbreak, and letting go.\n"
    "Audience: people struggling to move on from one-sided love and waiting for closure.\n"
    "Do not invent facts or change the quote meaning."
)

payload = {
    "script": script_content,
    "video_language": "english",
    "language": "english",
    "region": "global",
    "audience_type": "general",
    "target_audience": "people struggling to move on from one-sided love and waiting for closure",
    "viewer_promise": "emotional validation, quiet comfort, and strength to let go",
    "unique_angle": "silent heartbreak and accepting false hope without bitter resentment",
    "proof": "relatable emotional reflection and cinematic visual mood",
    "video_format": "Short",
    "title_style": "balanced",
    "thumbnail_idea": "rainy window at dusk with blurred amber taillights and on-screen quote text",
    "duration_seconds": 12.0,
    "exact_quote": "Hope can be cruel when it keeps you waiting for a person who will never return.",
    "on_screen_text": "Hope can be cruel when it keeps you waiting for a person who will never return.",
    "voice_over": "none",
    "visual_requirements": "Cinematic moody rainy city window at dusk, raindrops slowly sliding down the glass with soft blurred streetlights and distant taillights in the background.",
    "factual_claims": "None",
    "claim_restrictions": "Do not invent backstory, names, or false claims.",
    "creator_intent": "poetic quote video offering gentle reflection on false hope",
    "content_constraints": "preserve exact quote, no voice-over, no invented claims"
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/analyze",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

print("Sending request to http://127.0.0.1:8000/analyze...")
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        output_path = Path("runtime/artifacts/manual/generated_quote_response.json")
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
