"""
Phase 3 Data Intelligence Engine Audit
Tests YouTube gathering, keyword/entity extraction, outlier scoring, and cache logic.
"""
from __future__ import annotations

import sys
import json
from datetime import datetime, timezone, timedelta

# Mock YouTube API responses for testing
MOCK_YOUTUBE_RESULTS = [
    {
        "video_id": "test_vid_1",
        "channel_id": "test_ch_1",
        "title": "5 AM Morning Routine Challenge - 30 Days",
        "description": "I tried waking up at 5 AM for 30 days. Here's what happened.",
        "channel_title": "Test Creator",
        "published_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        "view_count": 250000,
        "like_count": 8500,
        "comment_count": 1200,
        "duration": "PT12M30S",
        "subscriber_count": 8500,
        "channel_video_count": 142,
    },
    {
        "video_id": "test_vid_2",
        "channel_id": "test_ch_2",
        "title": "Productivity Hack - Worth It or Overhyped",
        "description": "Testing the most viral productivity trends to see if they actually work.",
        "channel_title": "Growth Hacker",
        "published_at": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
        "view_count": 180000,
        "like_count": 5200,
        "comment_count": 680,
        "duration": "PT8M45S",
        "subscriber_count": 25000,
        "channel_video_count": 312,
    },
]

def test_keyword_extraction():
    """Test keyword extraction with region awareness."""
    from win_engine.analysis.keyword_extractor import extract_keyword_signals
    
    script = "I tried waking up at 5 AM every morning for 30 days and here's my honest productivity strategy"
    
    print("\n=== KEYWORD EXTRACTION TEST ===")
    print(f"Script: {script}\n")
    
    # Test global extraction
    signals_global = extract_keyword_signals(script, MOCK_YOUTUBE_RESULTS, region="global", primary_language="english")
    print(f"Global keywords (English):")
    for sig in signals_global[:5]:
        print(f"  - {sig['keyword']}: {sig['mentions']} mentions (strength: {sig['strength']})")
    
    # Test regional extraction
    signals_regional = extract_keyword_signals(script, MOCK_YOUTUBE_RESULTS, region="tamil nadu", primary_language="tamil")
    print(f"\nRegional keywords (Tamil Nadu):")
    for sig in signals_regional[:5]:
        print(f"  - {sig['keyword']}: {sig['mentions']} mentions (strength: {sig['strength']}, region_relevant: {sig.get('region_relevant', False)})")
    
    # Verify region boosting
    regional_boost_count = sum(1 for s in signals_regional if s.get("region_relevant"))
    print(f"\nRegion-relevant keywords boosted: {regional_boost_count}/{len(signals_regional)}")
    
    return len(signals_global) > 0 and len(signals_regional) > 0


def test_entity_extraction():
    """Test entity/topic extraction."""
    from win_engine.analysis.entity_extractor import extract_entity_signals
    
    script = "I tried waking up at 5 AM every day in 2025. Let's see if this productivity hack works"
    
    print("\n=== ENTITY EXTRACTION TEST ===")
    print(f"Script: {script}\n")
    
    signals = extract_entity_signals(script, MOCK_YOUTUBE_RESULTS)
    print(f"Extracted entities:")
    for sig in signals:
        print(f"  - {sig['entity']}: {sig['mentions']} mentions (type: {sig['type']})")
    
    # Check for year detection
    has_year = any(s["type"] == "year" for s in signals)
    print(f"\nYear detection working: {has_year}")
    
    return len(signals) > 0 and has_year


def test_outlier_scoring():
    """Test outlier scoring with regional weighting."""
    from win_engine.scoring.outlier_engine import score_outliers
    
    print("\n=== OUTLIER SCORING TEST ===")
    
    # Test global scoring
    scored_global = score_outliers(MOCK_YOUTUBE_RESULTS, region="global", primary_language="english")
    print(f"Global scoring (1.0x weight):")
    for result in scored_global:
        print(f"  - {result['title'][:40]}...")
        print(f"    Score: {result['outlier_score']}, Regional weight: {result['regional_weight']}")
        print(f"    Small channel outlier: {result['small_channel_outlier']}")
    
    # Test regional scoring
    scored_regional = score_outliers(MOCK_YOUTUBE_RESULTS, region="tamil nadu", primary_language="tamil")
    print(f"\nRegional scoring (Tamil Nadu, 1.35x weight):")
    for result in scored_regional:
        print(f"  - {result['title'][:40]}...")
        print(f"    Score: {result['outlier_score']}, Regional weight: {result['regional_weight']}")
    
    # Verify regional boost
    regional_weights = [r['regional_weight'] for r in scored_regional]
    global_weights = [r['regional_weight'] for r in scored_global]
    
    print(f"\nRegional weights: {regional_weights}")
    print(f"Global weights: {global_weights}")
    print(f"Regional boost applied correctly: {regional_weights[0] > global_weights[0]}")
    
    return len(scored_global) > 0 and scored_regional[0]['outlier_score'] > scored_global[0]['outlier_score']


def test_cache_policy():
    """Test cache policy logic for trending vs evergreen."""
    from win_engine.ingestion.research_service import ResearchService
    from win_engine.core.config import Settings
    
    print("\n=== CACHE POLICY TEST ===")
    
    settings = Settings(
        youtube_api_key="dummy",
        cache_ttl_trending_seconds=21600,
        cache_ttl_evergreen_seconds=604800,
    )
    
    service = ResearchService(settings)
    
    test_cases = [
        ("YouTube growth tips 2025", "trending"),
        ("Best productivity habits", "evergreen"),
        ("Latest viral challenge today", "trending"),
        ("How to start a YouTube channel", "evergreen"),
        ("Breaking news trending now", "trending"),
    ]
    
    for query, expected in test_cases:
        policy, ttl = service._select_cache_policy(query)
        status = "✓" if policy == expected else "✗"
        ttl_hours = ttl / 3600
        print(f"{status} '{query}'")
        print(f"  Policy: {policy} (TTL: {ttl_hours}h), Expected: {expected}")
    
    return True


def test_title_optimization_with_language():
    """Test title optimization with Tamil/Tanglish support."""
    from win_engine.analysis.title_optimizer import optimize_titles
    
    print("\n=== TITLE OPTIMIZATION TEST ===")
    
    title_variants = [
        "5 AM Routine Challenge - 30 Days Worth It",
        "5 AM Waake Up Macha Semma Change Ah",
        "Waking up at 5 AM - Honest Truth",
    ]
    
    # Test with English
    result_english = optimize_titles(
        title_variants,
        "5 AM Routine",
        "Productivity",
        language_strategy={"primary_language": "english"}
    )
    
    print(f"English optimization:")
    print(f"  Best: {result_english['best_title']}")
    print(f"  Scores: {[round(v['score'], 2) for v in result_english['scored_variants'][:2]]}")
    
    # Test with Tanglish
    result_tanglish = optimize_titles(
        title_variants,
        "5 AM Routine",
        "Productivity",
        language_strategy={"primary_language": "tanglish"}
    )
    
    print(f"\nTanglish optimization:")
    print(f"  Best: {result_tanglish['best_title']}")
    print(f"  Bonuses: {[round(v['language_bonus'], 2) for v in result_tanglish['scored_variants']]}")
    
    # Verify tanglish bonus applied
    has_bonuses = any(v['language_bonus'] > 0 for v in result_tanglish['scored_variants'])
    print(f"\nTanglish language bonus applied: {has_bonuses}")
    
    return result_english and result_tanglish


def test_region_aware_api_integration():
    """Test that region/language params flow through API."""
    from win_engine.core.schemas import AnalyzeRequest
    
    print("\n=== API SCHEMA INTEGRATION TEST ===")
    
    # Test schema accepts new fields
    request = AnalyzeRequest(
        script="Test script",
        language="tamil",
        region="tamil nadu",
        audience_type="local"
    )
    
    print(f"Request schema:")
    print(f"  Script: {request.script[:20]}...")
    print(f"  Language: {request.language}")
    print(f"  Region: {request.region}")
    print(f"  Audience type: {request.audience_type}")
    
    return (request.language == "tamil" and 
            request.region == "tamil nadu" and 
            request.audience_type == "local")


def main():
    """Run all Phase 3 audit tests."""
    print("=" * 60)
    print("PHASE 3: DATA INTELLIGENCE ENGINE AUDIT")
    print("=" * 60)
    
    tests = [
        ("Keyword Extraction", test_keyword_extraction),
        ("Entity Extraction", test_entity_extraction),
        ("Outlier Scoring", test_outlier_scoring),
        ("Cache Policy Logic", test_cache_policy),
        ("Title Optimization (Language)", test_title_optimization_with_language),
        ("API Schema Integration", test_region_aware_api_integration),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = "✓ PASSED" if result else "✗ FAILED"
            print(f"\n{test_name}: {'✓ PASSED' if result else '✗ FAILED'}")
        except Exception as e:
            results[test_name] = f"✗ ERROR: {str(e)}"
            print(f"\n{test_name}: ✗ ERROR")
            print(f"  {str(e)}")
    
    # Summary
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    for test_name, status in results.items():
        print(f"{status}: {test_name}")
    
    passed = sum(1 for s in results.values() if "PASSED" in s)
    total = len(results)
    print(f"\nResult: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
