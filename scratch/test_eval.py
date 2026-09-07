from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.generation_quality import evaluate_package_quality

script = """Format: YouTube Shorts
Visual: Rain drops on window pane at dusk, melancholic lofi mood
Voice-over: none
On-screen text: Hope can be cruel when it keeps you waiting for a person who will never return."""

brief = build_creator_brief(script=script)
quote_text = brief['exact_quote']
generated_pkg = {
    'title': 'When false hope keeps you waiting #shorts',
    'variants': ['When false hope keeps you waiting #shorts'],
    'description': f'"{quote_text}" A reflection on quiet heartbreak and knowing when to let go.',
    'tags': ['false hope', 'painful truth', 'moving on', 'heartbreak quotes', 'yt', 'shorts'],
    'hashtags': ['#shorts', '#FalseHope'],
}
evidence = {
    'content_terms': ['hope', 'cruel', 'waiting', 'person', 'return', 'false', 'painful', 'truth', 'moving', 'heartbreak', 'quotes', 'peace', 'letting', 'go', 'rain', 'dusk', 'window'],
    'candidates': [
        {'keyword': 'false hope', 'sources': ['model', 'research_query'], 'classification': 'core_topic', 'source_classification': 'combined', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 96, 'content_relevance_score': 42},
        {'keyword': 'painful truth', 'sources': ['model'], 'classification': 'secondary_topic', 'source_classification': 'script_derived', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 94, 'content_relevance_score': 42},
        {'keyword': 'moving on', 'sources': ['model', 'research_query'], 'classification': 'secondary_topic', 'source_classification': 'combined', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 92, 'content_relevance_score': 42},
        {'keyword': 'heartbreak quotes', 'sources': ['model'], 'classification': 'secondary_topic', 'source_classification': 'script_derived', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 90, 'content_relevance_score': 42},
    ],
    'selected_keywords': [
        {'keyword': 'false hope', 'classification': 'topic', 'source_classification': 'combined', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 95},
        {'keyword': 'painful truth', 'classification': 'topic', 'source_classification': 'script_derived', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 95},
        {'keyword': 'moving on', 'classification': 'topic', 'source_classification': 'combined', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 95},
        {'keyword': 'heartbreak quotes', 'classification': 'topic', 'source_classification': 'script_derived', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 95},
        {'keyword': 'yt', 'classification': 'platform_format', 'source_classification': 'creator_strategy', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 0},
        {'keyword': 'shorts', 'classification': 'platform_format', 'source_classification': 'creator_strategy', 'source_support_score': 100, 'source_support': 'support', 'keyword_relevance_score': 0},
    ]
}
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.feedback.history_store import HistoryStore
from unittest.mock import patch

research_data = {
    'main_topic': 'false hope',
    'keyword_signals': [{'keyword': 'false hope'}, {'keyword': 'moving on'}, {'keyword': 'letting go'}],
    'keyword_research': evidence,
    'entity_signals': [],
    'top_opportunities': [],
    'youtube_results': [],
    'research_queries': [],
    'category': 'quotes',
    'creator_brief': brief,
    'language_context': {'language': 'english', 'region': 'global', 'audience_type': 'general'},
    'history_store': HistoryStore(':memory:'),
}
context = {
    'language': 'english',
    'video_language': 'english',
    'region': 'global',
    'audience_type': 'general',
    'creator_brief': brief,
}
with patch('win_engine.llm.gemini_client.is_available', return_value=True), \
     patch('win_engine.generation.strategy_engine.write_multilang_packages_with_source', return_value=({'english': generated_pkg}, 'gemini')), \
     patch('win_engine.generation.quality_refinement.gemini_client.is_available', return_value=True):
    response = generate_seo_suggestions(script, research_data, context=context)

print("Title:", response["title"])
print("Tags:", response["tags"])
print("Verdict:", response["generation_quality"]["verdict"])
print("Warnings:", response["generation_quality"].get("warnings"))
print("Final quality:", response["generation_quality"]["final_seo_quality"])
