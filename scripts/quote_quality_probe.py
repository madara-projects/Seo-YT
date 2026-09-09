"""Run real quote requests against the local app; print reviewable evidence."""
import json
import sys
import urllib.request

for quote in sys.argv[1:]:
    payload = dict(script=quote, exact_quote=quote, on_screen_text=quote,
                   video_format="youtube_shorts", language="english",
                   video_language="english", region="global", title_style="balanced",
                   visual_requirements="A person walking along a quiet path at dusk. The quote is on screen.")
    request = urllib.request.Request("http://127.0.0.1:8000/analyze",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=240) as response:
        result = json.load(response)
    research = result.get("keyword_research", {})
    print(json.dumps({"quote": quote, **{k: result.get(k) for k in
        ("title", "description", "tags", "hashtags", "upload_timing", "research_queries", "research_warnings")},
        "quality": result.get("generation_quality", {}).get("final_seo_quality"),
        "evidence": research.get("selected_result_evidence"),
        "candidates": [{k: row.get(k) for k in ("keyword", "keyword_relevance_score", "evidence_count")}
            for row in research.get("candidates", [])],
        "rejected": research.get("rejected_candidates")}, ensure_ascii=True), flush=True)
