"""Regression evidence for the live Creator audit of 22 October 2026."""
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.retention_assistant import analyze_retention_assistant
from win_engine.analysis.research_insights import build_research_decision
from win_engine.analysis.research_planner import plan_research_queries
from win_engine.core.schemas import AnalyzeRequest
from win_engine.core.config import Settings
from win_engine.feedback.cloud_sync import safe_cloud_error, CloudSyncService
from win_engine.ingestion.research_service import ResearchService
from win_engine.ingestion.cache import TTLCache
from win_engine.llm import gemini_client

QUOTE = "One day you’re going to remember me and how much I loved you, and then you’re going to hate yourself for letting me go."


def test_description_context_survives_explicit_field_and_supported_scar_outcome():
    from win_engine.llm.seo_writer import _sanitize_generated_package, _validate
    quote = "When you are in love, and you get hurt, it’s like a cut. It will heal, but there will always be a scar."
    context = build_creator_brief(script=quote, exact_quote=quote, voice_over="none", video_format="youtube_shorts", duration_seconds=15)
    sentence = "A reflection on healing from hurt in love and the lasting emotional scars it leaves."
    raw = {"title": "Love heals but leaves a scar", "variants": ["The scar stays"], "description": quote, "description_context": sentence, "tags": [], "hashtags": []}
    result = _sanitize_generated_package(_validate(raw, short=True), quote, context)
    assert result["description"] == quote + "\n\n" + sentence
    assert result["_description_context_diagnostic"]["status"] == "retained"


def test_ambiguous_predictions_do_not_validate_foreign_scar_meaning():
    from win_engine.analysis.keyword_research import _ambiguous_predictions
    source = {"love", "hurt", "scar", "heal"}
    assert _ambiguous_predictions("scar quotes", {"suggestions": {"scar quotes": ["scar quotes", "scar quotes lion king", "scarface quotes", "scar secret life quotes"]}}, source)
    assert not _ambiguous_predictions("love quotes", {"suggestions": {"love quotes": ["love quotes", "love quotes in english", "love quotes in tamil", "love quotes for him"]}}, source)
    assert not _ambiguous_predictions("emotional scars quotes", {"suggestions": {}}, source)


def test_quote_research_uses_an_exact_quote_search_within_budget():
    quote = "Love can heal, but there will always be a scar."
    queries = plan_research_queries(script=quote, creator_brief={"exact_quote": quote, "video_format": "youtube_shorts", "voice_over": "none"}, semantic_analysis={"primary_topic": "emotional scars", "concept_evidence_validated": True}, max_queries=3)
    assert len(queries) <= 3
    assert {"type": "exact_quote", "query": '"' + quote + '"'} in queries


def test_scar_title_does_not_turn_love_into_the_cure():
    from win_engine.analysis.generation_quality import quote_title_issues
    quote = "When you are in love, and you get hurt, it’s like a cut. It will heal, but there will always be a scar."
    assert "unsupported_causal_claim" in {issue["code"] for issue in quote_title_issues("Love heals the cut, but the scar remains.", quote)}
    assert "unsupported_causal_claim" not in {issue["code"] for issue in quote_title_issues("Love heals the scars", "Love heals the scars.")}


def test_context_accepts_anchored_paraphrase_without_repeated_words():
    from win_engine.llm.seo_writer import _sanitize_generated_package
    quote = "Small steps every day can lead to big changes."
    context = build_creator_brief(script=quote, exact_quote=quote, video_format="youtube_shorts", voice_over="none")
    sentence = "A reflection on consistent effort and gradual progress."
    raw = {"title": quote, "description": quote, "description_context": sentence, "description_context_source_phrase": "Small steps every day", "tags": []}
    assert sentence in _sanitize_generated_package(raw, quote, context)["description"]
    raw["description_context_source_phrase"] = "Not present in source"
    assert sentence not in _sanitize_generated_package(raw, quote, context)["description"]


def test_music_metadata_cannot_turn_a_song_into_comparable_quote_evidence():
    from win_engine.analysis.quote_research_screen import screen_quote_results
    with patch.object(gemini_client, "generate") as generate:
        rows, status = screen_quote_results(QUOTE, [{"video_id": "song", "title": "LOVE SCARS OFFICIAL AUDIO NEW SONG", "description": QUOTE}])
    assert rows == []
    assert status == "no_candidates"
    generate.assert_not_called()


def test_silent_quote_description_drops_invented_story():
    from win_engine.llm.seo_writer import _sanitize_generated_package
    quote = "A tormented mind wants to forget, what a broken heart will always remember."
    context = build_creator_brief(script=quote, exact_quote=quote, voice_over="none", video_format="youtube_shorts", duration_seconds=12)
    package = _sanitize_generated_package({"title": "What a broken heart remembers", "description": quote + "\n\nMoving on is impossible after they abandoned you.", "tags": [], "hashtags": ["#BrokenHeart"]}, quote, context)
    assert package["description"] == quote


@pytest.mark.parametrize("sentence", [
    "A quote about wanting to forget while a broken heart holds on to memories.",
    "The quiet conflict of trying to let go while memory holds on.",
])
def test_silent_quote_description_keeps_one_grounded_context_sentence(sentence):
    from win_engine.llm.seo_writer import _sanitize_generated_package
    quote = "A tormented mind wants to forget, what a broken heart will always remember."
    context = build_creator_brief(script=quote, exact_quote=quote, voice_over="none", video_format="youtube_shorts", duration_seconds=12)
    package = _sanitize_generated_package({"title": "What a broken heart remembers", "description": quote + "\n\n" + sentence + " The mind and heart disagree forever.", "tags": [], "hashtags": []}, quote, context)
    assert package["description"] == quote + "\n\n" + sentence


@pytest.mark.parametrize("tag,rejected", [("why can't i forget someone", True), ("how to forget someone", True), ("broken heart quotes", False), ("mind vs heart quotes", False), ("why love hurts quotes", False)])
def test_quote_tags_distinguish_expression_from_advice(tag, rejected):
    from win_engine.analysis.keyword_research import _quote_advice_query
    assert _quote_advice_query(tag, "A tormented mind wants to forget, what a broken heart will always remember.") is rejected


def test_quote_topic_tags_keep_requested_platform_tags():
    from win_engine.analysis.keyword_research import build_keyword_research, select_final_tags
    from win_engine.analysis.generation_quality import feeling_hashtag
    quote = "A tormented mind wants to forget, what a broken heart will always remember."
    context = build_creator_brief(script=quote, exact_quote=quote, voice_over="none", video_format="youtube_shorts", duration_seconds=12)
    research = build_keyword_research(script=quote, semantic={"primary_topic": "broken heart quotes", "search_intents": ["mind quotes", "why can't i forget someone"], "concept_evidence_validated": True, "concept_evidence": [{"concept": "broken heart quotes", "source_phrase": "broken heart", "relationship": "direct", "source_scope": "content"}]}, youtube_results=[], research_queries=[], entity_signals=[], creator_brief=context)
    tags, evidence = select_final_tags(research, generated_tags=["broken heart quotes", "mind quotes", "why can't i forget someone"], title="What a broken heart remembers", script=quote, creator_brief=context)
    assert {"broken heart quotes", "yt", "shorts"} <= set(tags)
    assert not {"mind quotes", "why can't i forget someone"} & set(tags)
    assert all(item["intent"] == "emotional_relatable" for item in evidence["tag_provenance"] if item["tag"] not in {"yt", "shorts"})
    assert feeling_hashtag(quote) == "#heartbreak"


def brief():
    return build_creator_brief(script=QUOTE, exact_quote=QUOTE, voice_over="none", video_format="youtube_shorts", duration_seconds=20)


def test_reading_counts_pronouns_and_articles_without_changing_quote():
    result = analyze_retention_assistant(QUOTE, creator_brief=brief())
    assert result["quote_presentation"]["word_count"] == 24
    assert result["quote_presentation"]["estimated_single_read_seconds"] == 8.6
    assert result["first_frame"]["text_word_count"] == 24
    assert result["pacing"]["word_count"] == 24
    assert result["quote_presentation"]["exact_text_preserved_on_screen"] is True
    text = "I am a person with a purpose"
    value = analyze_retention_assistant(text, creator_brief=build_creator_brief(script=text, exact_quote=text))
    assert value["quote_presentation"]["word_count"] == 7


@pytest.mark.parametrize("alias,canonical", [("no", "none"), (" No ", "none"), ("silent", "none"), ("YES", "present"), ("unknown", "unknown"), ("", "")])
def test_voice_aliases_share_the_ui_contract(alias, canonical):
    assert AnalyzeRequest(script=QUOTE, voice_over=alias).voice_over == canonical
    if canonical:
        assert build_creator_brief(script=QUOTE, voice_over=alias)["voice_over"] == canonical


def test_invalid_voice_choice_is_rejected_before_research():
    with pytest.raises(ValidationError):
        AnalyzeRequest(script=QUOTE, voice_over="maybe no narration")


def test_research_filters_the_actual_off_topic_audit_results():
    rows = [
        {"title": "Taxi Driver’s Heartbreaking Loss — No Parent Should Ever Feel This Pain", "research_query": "emotional pain of loss", "description": "emotional pain loss love", "duration": "PT20S"},
        {"title": "middle class family #neetaspirents #emotional #pain #education", "research_query": "emotional pain of loss", "description": "emotional pain loss", "duration": "PT20S"},
        {"title": "PAIN DEATH #anime #naruto #emotional", "research_query": "emotional pain of loss", "description": "emotional pain loss", "duration": "PT20S"},
        {"title": "How to Heal Mental Pain PTSD Anxiety Depression", "research_query": "emotional pain of loss", "description": "emotional pain loss", "duration": "PT20S"},
        {"title": "the art of letting go without regret", "research_query": "regret letting someone go", "description": "", "duration": "PT20S"},
        {"title": "Regret after letting someone go", "research_query": "regret letting someone go", "description": "", "duration": "PT20S"},
    ]
    kept = ResearchService._filter_relevant_results(rows, brief())
    assert [row["title"] for row in kept] == ["Regret after letting someone go"]
    assert kept[0]["source_relevance_terms"]


def test_declared_bereavement_is_not_excluded():
    source = "I miss my mother after her death"
    b = build_creator_brief(script=source, exact_quote=source, video_format="youtube_shorts")
    rows = [{"title": "Missing my mother after her death", "research_query": "mother death", "duration": "PT30S"}]
    assert ResearchService._filter_relevant_results(rows, b)


def test_research_keeps_inflected_versions_of_the_same_query():
    rows = [{"title": "Regret after letting someone go", "research_query": "regretting letting someone go", "duration": "PT30S"}]
    assert ResearchService._filter_relevant_results(rows, brief())


def test_queries_do_not_broaden_the_quote_to_general_loss():
    queries = plan_research_queries(script=QUOTE, creator_brief=brief(), semantic_analysis={
        "primary_topic": "regret letting someone go", "secondary_topics": ["emotional pain of loss", "guilt"],
        "concept_evidence_validated": True,
    })
    assert queries
    assert all("emotional pain" not in row["query"] and "guilt" not in row["query"] for row in queries)


def test_repeat_run_drift_cases_do_not_pass_as_source_evidence():
    from win_engine.analysis.source_relevance import quote_result_support
    from win_engine.analysis.keyword_research import natural_tag_phrase
    from win_engine.analysis.semantic_research import usable_research_topic
    for title in ("Man Utd fans pick the player they regret letting go", "Forgive Yourself: The Secret to Letting Go of Regret", "When everything feels too much remember this"):
        assert quote_result_support(title, QUOTE)[0] is False
    assert natural_tag_phrase("going to remember this") is False
    assert usable_research_topic("one day you going remember how much loved") is False
    assert natural_tag_phrase("regret letting go") is True


def test_description_cannot_add_a_permanent_separation():
    from win_engine.analysis.generation_quality import evaluate_package_quality
    package = {"title": "You’re going to hate yourself for letting me go", "variants": [], "description": QUOTE + " Some realizations arrive only after the distance is permanent.", "tags": ["letting go", "yt", "shorts"], "hashtags": ["#shorts", "#quotes"]}
    result = evaluate_package_quality(package, script=QUOTE, creator_brief=brief())
    assert "unsupported_permanence" in {item["code"] for item in result["issues"]}


def test_catch_all_pattern_is_not_advice_or_high_semantic_confidence():
    rows = [{"title": "Quiet thoughts", "research_relevance_score": 100, "research_relevance_terms": ["quiet", "thoughts"]}] * 10
    decision = build_research_decision(brief(), rows)
    assert not any("dominant other" in note for note in decision["avoid"])
    assert decision["confidence"] != "high"


def response(status=200):
    value = MagicMock(status_code=status, headers={})
    value.json.return_value = {"candidates": [{"content": {"parts": [{"text": '{"ok":true}'}]}, "finishReason": "STOP"}]}
    return value


def test_retry_counts_survive_backup_switch_and_include_research():
    environment = {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "primary", "WIN_ENGINE_GEMINI_FALLBACK_MODEL": "backup", "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "1"}
    with patch.dict(os.environ, environment), patch.object(gemini_client.httpx, "post", side_effect=[response(500), response(500), response(), response()]), patch.object(gemini_client.time, "sleep"):
        with gemini_client.request_budget():
            _, first = gemini_client.generate_with_diagnostics("source", purpose="research")
            gemini_client.generate("package")
            total = gemini_client.request_diagnostics()
    assert first["backup_model_used"] is True
    assert first["attempts"] == 3 and first["retries"] == 2
    assert total["provider_attempts"] == 4 and total["provider_retries"] == 2
    assert [row["purpose"] for row in total["stages"]] == ["research", "package"]


def test_validated_semantics_cached_but_changed_source_reanalyzed():
    service = ResearchService(Settings(database_path=":memory:"))
    service._cache = TTLCache(60)
    analysis = {"source": "gemini", "concept_evidence_validated": True, "primary_topic": "letting go"}
    with patch("win_engine.ingestion.research_service.analyze_script_semantics", return_value=analysis) as call:
        service._cached_semantics(QUOTE, brief())
        assert service._cached_semantics(QUOTE, brief())["cache_status"] == "hit"
        service._cached_semantics("Different source", brief())
    assert call.call_count == 2


def test_cloud_error_categories_never_expose_driver_secrets():
    import pymysql
    for code, detail, category in [(1045, "user password=secret", "authentication"), (2003, "host private.example timed out", "timeout"), (2003, "SSL certificate private.example", "tls"), (2013, "lost server private.example", "connection")]:
        value = safe_cloud_error(pymysql.err.OperationalError(code, detail))
        assert value["category"] == category and value["code"] == code
        assert "secret" not in json.dumps(value) and "private.example" not in json.dumps(value)


def test_cloud_connection_retries_only_transient_setup_failures(tmp_path):
    import pymysql
    service = CloudSyncService(Settings(database_path=str(tmp_path / "test.db")))
    with patch("win_engine.feedback.cloud_sync._validated_ca_path", return_value=tmp_path / "ca.pem"), patch("pymysql.connect", side_effect=[pymysql.err.OperationalError(2003, "temporary connection failure"), "connected"]) as connect, patch("win_engine.feedback.cloud_sync.time.sleep"):
        assert service._remote_connection() == "connected"
        assert connect.call_count == 2
    with patch("win_engine.feedback.cloud_sync._validated_ca_path", return_value=tmp_path / "ca.pem"), patch("pymysql.connect", side_effect=pymysql.err.OperationalError(2003, "SSL certificate verify failed")) as connect:
        with pytest.raises(pymysql.err.OperationalError):
            service._remote_connection()
        assert connect.call_count == 1


def test_quote_screen_only_accepts_returned_ids_with_real_source_anchors():
    from win_engine.analysis.quote_research_screen import screen_quote_results
    rows = [{"video_id": "correct", "title": "Regretting letting someone go"}, {"video_id": "wrong", "title": "Let go of regret"}]
    answer = {"matches": [{"video_id": "correct", "source_anchor": "letting me go", "reason": "Regret after losing the person who loved them"}, {"video_id": "wrong", "source_anchor": "forgive yourself", "reason": "Not in source"}, {"video_id": "invented", "source_anchor": "letting me go", "reason": "Unknown ID"}]}
    with patch("win_engine.analysis.quote_research_screen.gemini_client.is_available", return_value=True), patch("win_engine.analysis.quote_research_screen.writer_reserve_reached", return_value=False), patch("win_engine.analysis.quote_research_screen.gemini_client.generate", return_value=json.dumps(answer)):
        kept, status = screen_quote_results(QUOTE, rows)
    assert status == "screened" and [row["video_id"] for row in kept] == ["correct"]
    assert kept[0]["source_relevance_basis"] == "model_screened_source_alignment"


@pytest.mark.parametrize("answer", ["", "not json", '{"matches":null}', '{"matches":[]}'])
def test_unavailable_or_empty_quote_screen_does_not_invent_evidence(answer):
    from win_engine.analysis.quote_research_screen import screen_quote_results
    with patch("win_engine.analysis.quote_research_screen.gemini_client.is_available", return_value=True), patch("win_engine.analysis.quote_research_screen.writer_reserve_reached", return_value=False), patch("win_engine.analysis.quote_research_screen.gemini_client.generate", return_value=answer):
        kept, _ = screen_quote_results(QUOTE, [{"video_id": "v", "title": "A nearby mood"}])
    assert kept == []
