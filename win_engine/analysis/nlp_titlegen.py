import spacy
from typing import List, Tuple

nlp = spacy.load("en_core_web_sm")

def extract_main_subject_action(text: str) -> Tuple[str, str]:
    doc = nlp(text)
    subject = ""
    action = ""
    for sent in doc.sents:
        for token in sent:
            if token.dep_ in ("nsubj", "nsubjpass") and not subject:
                subject = token.text
            if token.pos_ == "VERB" and not action:
                action = token.lemma_
        if subject and action:
            break
    return subject, action

def extract_keywords(text: str, top_n: int = 5) -> List[str]:
    doc = nlp(text)
    # Use noun chunks and named entities for richer keywords
    keywords = set()
    for chunk in doc.noun_chunks:
        if len(chunk.text) > 2:
            keywords.add(chunk.text.strip())
    for ent in doc.ents:
        keywords.add(ent.text.strip())
    # Add top frequent nouns/adjectives
    freq = {}
    for token in doc:
        if token.pos_ in {"NOUN", "PROPN", "ADJ"} and not token.is_stop:
            freq[token.lemma_.lower()] = freq.get(token.lemma_.lower(), 0) + 1
    sorted_freq = sorted(freq.items(), key=lambda x: -x[1])
    for word, _ in sorted_freq[:top_n]:
        keywords.add(word)
    return list(keywords)[:top_n]

def generate_dynamic_title(text: str) -> str:
    subject, action = extract_main_subject_action(text)
    keywords = extract_keywords(text)
    # SEO pattern: [How/Why/What] + [action/subject] + [main keyword/benefit]
    if subject and action and keywords:
        return f"How to {action} {subject} for {keywords[0]} | {keywords[1] if len(keywords)>1 else ''}"
    elif keywords:
        return f"{keywords[0].capitalize()}: {keywords[1] if len(keywords)>1 else ''} - YouTube Growth Tips"
    else:
        return "Proven YouTube Strategy for Growth"

def generate_dynamic_description(text: str) -> str:
    keywords = extract_keywords(text, top_n=7)
    summary = text.strip().replace('\n', ' ')
    desc = f"This video covers: {', '.join(keywords)}. {summary[:200]}...\nLearn actionable strategies for YouTube success, SEO, and audience growth."
    return desc
