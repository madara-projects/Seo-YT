#!/usr/bin/env python3
"""
Test and analyze the description generation quality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from win_engine.analysis.nlp_titlegen import generate_dynamic_description

def test_description_generation():
    """Test the description generation and analyze its quality"""
    # Test with a more comprehensive script
    script = """Welcome to this comprehensive guide on how to grow your YouTube channel from 0 to 10,000 subscribers. Today I'm going to share the exact strategies that helped me reach 10k subscribers in just 6 months. We'll cover thumbnail optimization, title creation, SEO techniques, and content planning. First, let's talk about the importance of eye-catching thumbnails. Your thumbnail is the first thing viewers see, and it can make or break your click-through rate. I'll show you how to design thumbnails that get 50% more clicks. Next, we'll dive into title optimization - the art of creating titles that are both SEO-friendly and clickbait-worthy. Then we'll cover the YouTube algorithm and how to optimize your videos for maximum visibility. Finally, I'll share my content calendar template that you can use to plan your videos for consistent growth."""

    print("🎬 Testing YouTube Description Generation")
    print("=" * 60)
    print(f"Script Length: {len(script)} characters")
    print()

    # Generate description
    description = generate_dynamic_description(script)

    print("📝 GENERATED DESCRIPTION:")
    print("-" * 40)
    print(description)
    print("-" * 40)
    print()

    # Analyze the description
    analysis = analyze_description_quality(description, script)

    print("📊 DESCRIPTION ANALYSIS:")
    print(f"Length: {len(description)} characters")
    print(f"Word Count: {len(description.split())} words")
    print(f"Score: {analysis['overall_score']}/10")
    print()

    print("✅ STRENGTHS:")
    for strength in analysis['strengths']:
        print(f"  • {strength}")

    print()
    print("⚠️  WEAKNESSES:")
    for weakness in analysis['weaknesses']:
        print(f"  • {weakness}")

    print()
    print("💡 IMPROVEMENTS NEEDED:")
    for improvement in analysis['improvements']:
        print(f"  • {improvement}")

    return analysis

def analyze_description_quality(description, script):
    """Analyze description quality against YouTube best practices"""

    analysis = {
        'overall_score': 0,
        'strengths': [],
        'weaknesses': [],
        'improvements': []
    }

    # Length analysis (YouTube descriptions should be 125-5000 characters, ideally 150-300)
    length = len(description)
    if 150 <= length <= 300:
        analysis['overall_score'] += 2
        analysis['strengths'].append("Optimal length for YouTube engagement")
    elif 125 <= length <= 500:
        analysis['overall_score'] += 1.5
        analysis['strengths'].append("Good length range")
    elif length < 125:
        analysis['weaknesses'].append("Too short - missing key elements")
    else:
        analysis['weaknesses'].append("Too long - may overwhelm viewers")

    # Content analysis
    desc_lower = description.lower()

    # Hook/Introduction (first 50 characters should be engaging)
    first_50 = description[:50]
    if any(word in first_50.lower() for word in ['🎥', 'video', 'share', 'learn', 'discover', 'watch']):
        analysis['overall_score'] += 1
        analysis['strengths'].append("Strong opening hook")
    else:
        analysis['improvements'].append("Add more engaging opening hook")

    # Call to Action
    cta_elements = ['like', 'subscribe', 'comment', 'share', 'follow', '👍', '💬', '🔗']
    cta_count = sum(1 for element in cta_elements if element in desc_lower)
    if cta_count >= 3:
        analysis['overall_score'] += 1.5
        analysis['strengths'].append("Strong call-to-action elements")
    elif cta_count >= 2:
        analysis['overall_score'] += 1
        analysis['strengths'].append("Good call-to-action presence")
    else:
        analysis['improvements'].append("Add more call-to-action elements")

    # Timestamps
    if 'timestamps' in desc_lower or '⏱️' in description:
        analysis['overall_score'] += 1
        analysis['strengths'].append("Includes timestamps for navigation")
    else:
        analysis['improvements'].append("Add chapter timestamps")

    # Hashtags
    hashtag_count = description.count('#')
    if hashtag_count >= 3:
        analysis['overall_score'] += 1
        analysis['strengths'].append("Good hashtag usage")
    elif hashtag_count >= 1:
        analysis['overall_score'] += 0.5
        analysis['strengths'].append("Some hashtags present")
    else:
        analysis['improvements'].append("Add relevant hashtags")

    # Emojis
    emoji_count = sum(1 for char in description if ord(char) > 127)
    if emoji_count >= 5:
        analysis['overall_score'] += 1
        analysis['strengths'].append("Good visual appeal with emojis")
    elif emoji_count >= 3:
        analysis['overall_score'] += 0.5
        analysis['strengths'].append("Some emoji usage")
    else:
        analysis['improvements'].append("Add more emojis for visual appeal")

    # Keyword integration
    script_keywords = ['instagram', 'upload', 'videos', 'how to']
    keyword_count = sum(1 for keyword in script_keywords if keyword in desc_lower)
    if keyword_count >= len(script_keywords) * 0.75:
        analysis['overall_score'] += 1
        analysis['strengths'].append("Good keyword integration")
    elif keyword_count >= len(script_keywords) * 0.5:
        analysis['overall_score'] += 0.5
        analysis['strengths'].append("Some keyword usage")
    else:
        analysis['improvements'].append("Better keyword integration")

    # Structure analysis
    lines = description.split('\n')
    if len(lines) >= 8:  # Good structure with multiple sections
        analysis['overall_score'] += 1
        analysis['strengths'].append("Well-structured with clear sections")
    elif len(lines) >= 5:
        analysis['overall_score'] += 0.5
        analysis['strengths'].append("Decent structure")
    else:
        analysis['improvements'].append("Improve description structure")

    # SEO elements
    seo_elements = ['links in description', '🔗', 'check out', 'learn more']
    seo_count = sum(1 for element in seo_elements if element in desc_lower)
    if seo_count >= 2:
        analysis['overall_score'] += 1
        analysis['strengths'].append("Good SEO elements")
    elif seo_count >= 1:
        analysis['overall_score'] += 0.5
        analysis['strengths'].append("Some SEO elements")
    else:
        analysis['improvements'].append("Add SEO elements (links, resources)")

    # Engagement elements
    engagement_words = ['comment', 'question', 'feedback', 'share your thoughts', 'let me know']
    engagement_count = sum(1 for word in engagement_words if word in desc_lower)
    if engagement_count >= 2:
        analysis['overall_score'] += 1
        analysis['strengths'].append("Strong engagement prompts")
    elif engagement_count >= 1:
        analysis['overall_score'] += 0.5
        analysis['strengths'].append("Some engagement elements")
    else:
        analysis['improvements'].append("Add engagement prompts")

    # Cap the score at 10
    analysis['overall_score'] = round(min(analysis['overall_score'], 10.0), 1)

    # Overall assessment
    if analysis['overall_score'] >= 8:
        analysis['strengths'].insert(0, "Excellent description - ready for high performance")
    elif analysis['overall_score'] >= 6:
        analysis['strengths'].insert(0, "Good description with solid foundation")
    elif analysis['overall_score'] >= 4:
        analysis['strengths'].insert(0, "Decent description - needs improvement")
    else:
        analysis['weaknesses'].insert(0, "Poor description quality - major improvements needed")

    return analysis

if __name__ == "__main__":
    test_description_generation()