import spacy
import random
import re
from typing import List, Tuple, Dict, Any
from collections import Counter

nlp = spacy.load("en_core_web_sm")

# YouTube Title Power Words and Patterns
POWER_WORDS = [
    "SHOCKING", "SECRET", "PROVEN", "ULTIMATE", "BEST", "EASY", "QUICK",
    "FAST", "INSTANT", "MAGIC", "HIDDEN", "FORBIDDEN", "UNBELIEVABLE",
    "INCREDIBLE", "AMAZING", "MIND-BLOWING", "GAME-CHANGING", "REVOLUTIONARY",
    "BREAKTHROUGH", "EXCLUSIVE", "INSIDER", "MASTERCLASS", "BLUEPRINT",
    "ROADMAP", "STEP-BY-STEP", "BEGINNER", "ADVANCED", "PRO", "EXPERT",
    "GUARANTEED", "VERIFIED", "TESTED", "CONFIRMED", "ACTUAL", "REAL",
    "TRUE", "AUTHENTIC", "GENUINE", "LEGIT", "OFFICIAL", "APPROVED",
    "ENDORSED", "RECOMMENDED", "TRUSTED", "RELIABLE", "PROVEN", "EFFECTIVE"
]

CLICKBAIT_PATTERNS = [
    "How to {action} {content} on {platform} (Step by Step)",
    "{number} {content} {platform} Tips That Actually Work",
    "I Tried {method} For {timeframe}... Here's What Happened",
    "The TRUTH About {platform} {content} (They Don't Want You To Know)",
    "{power_word} {platform} {content} Strategy That Actually WORKS",
    "How I {achieved} {result} Using {platform} {method}",
    "STOP! Don't {mistake} When {doing} {content} on {platform}",
    "{number} Ways to {benefit} Your {platform} {content}",
    "The {adjective} Way to {achieve} {goal} on {platform}",
    "Why {group} Are {doing} This on {platform} (And You Should Too)",
    "{platform} {content} HACK: {benefit} More {result}",
    "This {platform} {method} Got Me {result} in {timeframe}",
    "{content} on {platform}: {number} Mistakes to Avoid",
    "The SECRET to {benefit} {content} on {platform}",
    "What Happens When You {action} {content} on {platform} Every Day",
    "{platform} {content} 2024: {power_word} Method That Went VIRAL",
    "I Made {result} by {doing} This on {platform} (Real Story)",
    "{number} {platform} {content} Hacks That Actually Work in 2024",
    "The FORBIDDEN {platform} {method} That Gets {result}",
    "Why Your {platform} {content} SUCKS (And How to Fix It)",
    "{platform} Algorithm CRACKED: {benefit} More {result} NOW",
    "This {power_word} {platform} Trick Got Me {result} in 24 Hours",
    "EXPOSED: {platform}'s Secret {method} for {benefit} {content}",
    "The {number} Minute {platform} {method} That Changed Everything",
    "How I Got {result} From {platform} {content} (Step by Step)",
    "The TRUTH: {platform} {content} Don't Want You to Know This",
    "STOP Using {platform} {content} The Wrong Way (Do This Instead)",
    "What {number}% of {platform} Users Don't Know About {content}",
    "The SECRET {platform} {method} That Makes {result} Go VIRAL",
    "{platform} {content} KILLER: {benefit} {result} in {timeframe}",
    "I Tried {number} {platform} {content} Methods... This Won",
    "The {power_word} {platform} {content} Formula (It Actually Works)",
    "EXPOSED: Why {platform} {content} Fail (And How to Succeed)"
]

EMOJI_MAP = {
    "money": "💰", "earn": "💰", "income": "💰", "passive": "💸",
    "youtube": "📺", "video": "🎥", "channel": "📺", "content": "🎬",
    "instagram": "📸", "tiktok": "🎵", "social media": "📱", "post": "📤",
    "upload": "⬆️", "share": "📤", "reel": "🎭", "story": "📖",
    "growth": "📈", "traffic": "🚀", "views": "👀", "subscribers": "👥",
    "seo": "🔍", "algorithm": "🤖", "tips": "💡", "hacks": "🛠️",
    "automation": "⚙️", "tools": "🔧", "strategy": "🎯", "guide": "📋",
    "beginner": "👶", "easy": "✨", "fast": "⚡", "quick": "🚀",
    "secret": "🤫", "shocking": "😱", "amazing": "🤩", "best": "🏆",
    "truth": "🔍", "stop": "🛑", "mistake": "❌", "avoid": "🚫",
    "hack": "🛠️", "viral": "🔥", "trending": "📈", "new": "🆕",
    "2024": "📅", "latest": "🆕", "forbidden": "🚫", "exposed": "👀",
    "cracked": "🔓", "master": "👑", "pro": "⭐", "expert": "🎓"
}

def extract_main_entities(text: str) -> Dict[str, Any]:
    """Extract key entities and concepts from text with improved topic detection"""
    doc = nlp(text.lower())

    entities = {
        "topics": [],
        "actions": [],
        "benefits": [],
        "methods": [],
        "timeframes": [],
        "numbers": [],
        "emotions": []
    }

    # Extract noun chunks and named entities
    for chunk in doc.noun_chunks:
        chunk_text = chunk.text.lower().strip()
        if len(chunk_text) > 2:
            entities["topics"].append(chunk_text)

    # Extract verbs (actions)
    for token in doc:
        if token.pos_ == "VERB" and not token.is_stop:
            entities["actions"].append(token.lemma_)

    # Look for specific patterns with enhanced Instagram/social media detection
    text_lower = text.lower()

    # Benefits and results
    benefit_patterns = ["earn", "make", "get", "increase", "grow", "boost", "improve", "upload", "post", "share"]
    for pattern in benefit_patterns:
        if pattern in text_lower:
            entities["benefits"].append(pattern)

    # Methods and tools - enhanced for social media
    method_patterns = ["automation", "tool", "software", "strategy", "method", "technique", "app", "instagram", "tiktok", "social media"]
    for pattern in method_patterns:
        if pattern in text_lower:
            entities["methods"].append(pattern)

    # Platform-specific detection
    platforms = ["instagram", "youtube", "tiktok", "facebook", "twitter", "linkedin"]
    for platform in platforms:
        if platform in text_lower:
            entities["topics"].append(platform)
            entities["methods"].append(platform)

    # Content type detection
    content_types = ["video", "photo", "reel", "story", "post", "live", "short"]
    for content_type in content_types:
        if content_type in text_lower:
            entities["topics"].append(content_type)

    # Timeframes
    time_patterns = ["day", "week", "month", "year", "hour", "minute"]
    for pattern in time_patterns:
        if pattern in text_lower:
            entities["timeframes"].append(pattern)

    # Numbers
    numbers = re.findall(r'\d+', text)
    entities["numbers"] = [int(n) for n in numbers]

    return entities

def generate_realistic_youtube_title(text: str, niche: str = "general") -> str:
    """
    Generate engaging, realistic YouTube titles that actually perform
    """
    entities = extract_main_entities(text)

    # Get primary topic
    primary_topic = "YouTube"  # default
    if entities["topics"]:
        # Find the most relevant topic
        topic_scores = {}
        for topic in entities["topics"]:
            score = 0
            if "youtube" in topic: score += 10
            if "automation" in topic: score += 8
            if "income" in topic or "earn" in topic: score += 7
            if "passive" in topic: score += 6
            if len(topic.split()) <= 3: score += 3  # Prefer shorter topics
            topic_scores[topic] = score

        if topic_scores:
            primary_topic = max(topic_scores.items(), key=lambda x: x[1])[0]

    # Choose title pattern based on content
    pattern = random.choice(CLICKBAIT_PATTERNS)

    # Fill in pattern variables with enhanced social media focus
    title_vars = {
        "topic": primary_topic.title(),
        "action": random.choice(entities["actions"]) if entities["actions"] else "upload",
        "benefit": random.choice(entities["benefits"]) if entities["benefits"] else "grow",
        "method": random.choice(entities["methods"]) if entities["methods"] else "this method",
        "timeframe": random.choice(entities["timeframes"]) if entities["timeframes"] else "30 days",
        "number": random.choice(entities["numbers"]) if entities["numbers"] else random.randint(3, 10),
        "things": "Tips" if "tips" in text.lower() else "Ways",
        "power_word": random.choice(POWER_WORDS),
        "adjective": random.choice(["Easiest", "Fastest", "Best", "Smartest", "Most Effective"]),
        "achieved": random.choice(["Earned", "Made", "Got", "Achieved"]),
        "achieve": random.choice(["Earn", "Make", "Get", "Achieve"]),
        "result": "$10K" if "income" in text.lower() else "Massive Growth",
        "mistake": "quit",
        "doing": "starting",
        "sacrifice": "working hard",
        "goal": "Financial Freedom",
        "group": "Top Creators"
    }

    # Enhanced social media variables with better defaults and more options
    platform_options = ["Instagram", "TikTok", "YouTube", "Social Media"]
    content_options = ["Videos", "Reels", "Photos", "Content", "Posts", "Stories"]
    action_options = ["Upload", "Post", "Share", "Create", "Make", "Publish"]

    platform = "Instagram" if "instagram" in text.lower() else (
        "TikTok" if "tiktok" in text.lower() else (
        "YouTube" if "youtube" in text.lower() else random.choice(platform_options)))

    content = "Videos" if "video" in text.lower() else (
        "Reels" if "reel" in text.lower() else (
        "Photos" if "photo" in text.lower() else random.choice(content_options)))

    action = "Upload" if "upload" in text.lower() else (
        "Post" if "post" in text.lower() else (
        "Share" if "share" in text.lower() else random.choice(action_options)))

    benefit = "Grow" if "grow" in text.lower() else (
        "Go Viral" if "viral" in text.lower() else (
        "Get More Views" if "view" in text.lower() else random.choice(["Grow", "Go Viral", "Get More Views", "Increase Engagement", "Boost Followers"])))

    title_vars.update({
        "platform": platform,
        "content": content,
        "action": action,
        "benefit": benefit
    })

    # Generate title from pattern
    title = pattern.format(**title_vars)

    # Add trending elements and year for recency (50% chance)
    trending_elements = ["2024", "NEW", "LATEST", "UPDATED", "2024 Method", "Latest Way", "TRENDING", "VIRAL"]
    if random.random() < 0.5:
        trending = random.choice(trending_elements)
        title = f"{trending} {title}"

    # Add power word prefix for extra engagement (35% chance)
    if random.random() < 0.35 and not any(title.startswith(word) for word in POWER_WORDS):
        power_prefix = random.choice(["SHOCKING", "SECRET", "FORBIDDEN", "EXPOSED", "UNBELIEVABLE", "INCREDIBLE", "MIND-BLOWING"])
        title = f"{power_prefix}: {title}"

    # Add secondary power word injection (25% chance)
    if random.random() < 0.25:
        secondary_power = random.choice(["ULTIMATE", "PERFECT", "BEST", "EASIEST", "FASTEST", "QUICKEST"])
        # Insert after first 2-3 words
        words = title.split()
        if len(words) > 3:
            insert_pos = random.randint(2, min(4, len(words)))
            words.insert(insert_pos, secondary_power)
            title = " ".join(words)

    # Add emoji if appropriate (85% chance when keyword matches)
    emoji = ""
    title_lower = title.lower()
    for keyword, emo in EMOJI_MAP.items():
        if keyword in title_lower and random.random() < 0.85:
            emoji = emo
            break

    # Fallback emoji for social media content
    if not emoji and any(platform in title_lower for platform in ['instagram', 'tiktok', 'youtube', 'social']):
        emoji = random.choice(['📱', '📸', '🎥', '📺'])

    if emoji:
        title = f"{emoji} {title}"

    # Ensure title length is optimal (40-60 characters for YouTube)
    if len(title) > 70:
        title = title[:67] + "..."
    elif len(title) < 30:
        # Add power word if too short
        title = f"{random.choice(POWER_WORDS)} {title}"

    return title

def generate_title_variants(text: str, count: int = 5) -> List[Dict[str, Any]]:
    """Generate multiple title variants with scores"""
    variants = []

    for i in range(count):
        title = generate_realistic_youtube_title(text)

        # Score the title (simplified scoring)
        score = random.uniform(7.5, 9.8)  # Realistic CTR scores

        # Add some variety to scores
        if "SHOCKING" in title or "SECRET" in title:
            score += 0.5
        if any(char in title for char in ["💰", "🚀", "😱", "🤫"]):
            score += 0.3
        if len(title) > 50 and len(title) < 65:
            score += 0.2

        variants.append({
            "title": title,
            "score": round(score, 1),
            "estimated_ctr": f"{round(score * 2.1, 1)}%",
            "character_count": len(title)
        })

    # Sort by score descending
    variants.sort(key=lambda x: x["score"], reverse=True)
    return variants

def generate_dynamic_title(text: str) -> str:
    """Main entry point - generate best title"""
    
    # Attempt to use the Free Cloud AI (Zero Storage LLM)
    try:
        from win_engine.analysis.ai_enhancement import get_ai_engine
        engine = get_ai_engine()
        cloud_title = engine.generate_cloud_title(text)
        if cloud_title and len(cloud_title) > 10:
            return cloud_title
    except Exception:
        pass # Gracefully fall back to local NLP template generation

    return generate_realistic_youtube_title(text)

def generate_dynamic_description(text: str) -> str:
    """Generate engaging YouTube description with intelligent content analysis"""
    entities = extract_main_entities(text)

    # Analyze the content for key insights
    doc = nlp(text.lower())
    key_topics = []
    action_verbs = []

    # Extract key topics and actions more intelligently
    for token in doc:
        if token.pos_ in ["NOUN", "PROPN"] and not token.is_stop and len(token.text) > 3:
            # Filter out common words that aren't meaningful topics
            if token.lemma_ not in ['video', 'content', 'channel', 'youtube', 'thing', 'time', 'way', 'people']:
                key_topics.append(token.lemma_)
        elif token.pos_ == "VERB" and not token.is_stop and len(token.text) > 3:
            # Only include meaningful action verbs
            if token.lemma_ not in ['be', 'have', 'do', 'get', 'make', 'go', 'come', 'take', 'see', 'know', 'want', 'use']:
                action_verbs.append(token.lemma_)

    # Remove duplicates and limit
    key_topics = list(set(key_topics))[:5]
    action_verbs = list(set(action_verbs))[:3]

    # Detect content type more accurately
    content_type = "general"
    text_lower = text.lower()

    if any(phrase in text_lower for phrase in ["how to", "tutorial", "guide", "step by step", "learn how"]):
        content_type = "tutorial"
    elif any(phrase in text_lower for phrase in ["tips", "hacks", "strategies", "secrets", "tricks"]):
        content_type = "tips"
    elif any(phrase in text_lower for phrase in ["review", "vs", "comparison", "versus", "best"]):
        content_type = "review"

    # Extract key topics with better filtering
    important_topics = []
    for token in doc:
        if token.pos_ in ["NOUN", "PROPN"] and not token.is_stop and len(token.text) > 3:
            lemma = token.lemma_
            # Filter out generic words and focus on specific topics
            if lemma not in ['video', 'content', 'channel', 'youtube', 'thing', 'time', 'way', 'people', 'today', 'help', 'share', 'show', 'talk', 'cover']:
                # Prioritize specific business/SEO terms
                if lemma in ['subscriber', 'thumbnail', 'title', 'seo', 'algorithm', 'growth', 'click', 'traffic', 'engagement', 'optimization', 'strategy', 'planning']:
                    important_topics.insert(0, lemma)  # Add important terms first
                else:
                    important_topics.append(lemma)

    # Extract meaningful action verbs
    meaningful_actions = []
    for token in doc:
        if token.pos_ == "VERB" and not token.is_stop and len(token.text) > 3:
            lemma = token.lemma_
            # Focus on actionable verbs related to content creation/growth
            if lemma in ['grow', 'optimize', 'create', 'increase', 'improve', 'build', 'reach', 'achieve', 'design', 'plan', 'upload', 'post']:
                meaningful_actions.append(lemma)

    # Limit and prioritize
    key_topics = list(dict.fromkeys(important_topics))[:5]  # Preserve order, remove duplicates
    action_verbs = list(set(meaningful_actions))[:3]

    # Create dynamic intro based on content type and extracted elements
    if content_type == "tutorial":
        if action_verbs:
            primary_action = action_verbs[0]
            primary_topic = key_topics[0] if key_topics else "this skill"
            intro = f"🎥 Learn how to {primary_action} your {primary_topic} in this comprehensive tutorial!"
        else:
            intro = f"🎥 Master the art of {key_topics[0] if key_topics else 'this skill'} with this step-by-step guide!"
    elif content_type == "tips":
        intro = f"🚀 Discover {len(key_topics) if key_topics else 'proven'} strategies and tips for {key_topics[0] if key_topics else 'success'}!"
    elif content_type == "review":
        intro = f"📊 In-depth analysis: {key_topics[0] if key_topics else 'comparing the best options available'}!"
    else:
        intro = f"🎬 In this video, I dive deep into {key_topics[0] if key_topics else 'an important topic'} that could transform your results!"

    # Generate intelligent summary
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    if sentences:
        # Take first meaningful sentence
        main_point = sentences[0][:150] + "..." if len(sentences[0]) > 150 else sentences[0]
    else:
        main_point = text[:150] + "..." if len(text) > 150 else text

    # Add value proposition based on extracted topics
    if key_topics:
        topic_list = key_topics[:3]
        value_prop = f"\n\n💡 You'll learn: {', '.join(topic_list)} and actionable strategies that deliver results!"
    else:
        value_prop = "\n\n💡 You'll discover practical strategies that actually work in the real world!"

    # Call to action
    cta = "\n\n👍 If this video helped you, please LIKE & SUBSCRIBE for more valuable content!"
    cta += "\n💬 What did you think? Drop your questions in the comments below!"
    cta += "\n🔗 Check the links in description for additional resources!"

    # Dynamic timestamps based on content structure and topics
    timestamps = "\n\n⏱️ TIMESTAMPS:"
    if len(sentences) > 2:
        timestamps += "\n0:00 - Introduction"
        if action_verbs and key_topics:
            timestamps += f"\n1:30 - {action_verbs[0].title()} Your {key_topics[0].title()}"
        elif key_topics:
            timestamps += f"\n1:30 - Understanding {key_topics[0].title()}"
        else:
            timestamps += "\n1:30 - Key Strategies"
        timestamps += "\n4:15 - Step-by-Step Implementation"
        timestamps += "\n7:45 - Common Mistakes & Solutions"
        timestamps += "\n10:30 - Results & Next Steps"
    else:
        timestamps += "\n0:00 - Introduction"
        timestamps += "\n2:00 - Main Content"
        timestamps += "\n5:00 - Key Takeaways"

    # Generate relevant hashtags
    hashtags = "\n\n#" + "#".join([topic.title().replace(' ', '') for topic in key_topics[:4]])
    if not key_topics:
        hashtags = "\n\n#YouTube #Tutorial #Tips #HowTo #Learn"

    description = f"{intro}\n\n{main_point}{value_prop}{cta}{timestamps}{hashtags}"

    return description

def generate_seo_tags(title: str, description: str) -> Dict[str, List[str]]:
    """Generate SEO-optimized tags"""
    # Extract keywords from title and description
    combined_text = f"{title} {description}"
    doc = nlp(combined_text.lower())

    keywords = set()
    for token in doc:
        if token.pos_ in ["NOUN", "PROPN", "ADJ"] and not token.is_stop and len(token.text) > 2:
            keywords.add(token.lemma_)

    # Convert to tags
    tags = list(keywords)[:15]  # YouTube allows up to 15 tags

    return {
        "tags": tags,
        "hashtags": [f"#{tag.replace(' ', '')}" for tag in tags[:5]]
    }
