#!/usr/bin/env python3
"""
Enhanced Language Detection Engine with Tamil Script Support
Supports: English, Tamil, Hindi, Spanish, French, Portuguese
Author: Win-Engine Development Team
Date: April 2026
"""

import re
import unicodedata
from typing import Dict, Tuple, Optional

class TamilLanguageDetector:
    """
    Detects and processes Tamil, Tanglish (Tamil in English), and other languages
    Tamil Unicode Range: U+0B80 - U+0BFF
    """
    
    # Tamil character ranges
    TAMIL_CHARS = re.compile(r'[\u0B80-\u0BFF]+')
    
    # Tamil vowels, consonants, vowel modifiers
    TAMIL_VOWELS = 'அ ஆ இ ஈ உ ஊ எ ஏ ஐ ஒ ஓ ஔ'
    TAMIL_CONSONANTS = 'க கா கி கீ கு கூ கெ கே கை கொ கோ கௌ'
    
    # Vowel modifiers (aanai, etc.)
    TAMIL_VOWEL_MODIFIERS = ['ா', 'ி', 'ீ', 'ு', 'ூ', 'ெ', 'ே', 'ै', 'ொ', 'ோ', 'ௌ']
    
    # Tanglish patterns (Tamil words in English script)
    TANGLISH_PATTERNS = {
        'panna': 'பண்ண',  # do/make
        'pannuven': 'பண்ணுவேன்',  # I will do
        'pannurom': 'பண்ணுரோம்',  # we will do
        'automation': 'ஆடோமேஷன்',  # automation
        'passive': 'பேசிவ்',  # passive
        'income': 'இன்கம்',  # income
        'pannlam': 'பண்ணலாம்',  # can do
        'youtube': 'யூடியூப்',  # YouTube
        'explain': 'எக்ஸ்ப்ளெயின்',  # explain
        'moola': 'மூல',  # base/root
        'earn': 'எர்ன்',  # earn
    }
    
    @staticmethod
    def has_tamil_script(text: str) -> bool:
        """Check if text contains Tamil characters"""
        return bool(TamilLanguageDetector.TAMIL_CHARS.search(text))
    
    @staticmethod
    def tamil_character_count(text: str) -> int:
        """Count Tamil characters in text"""
        return len(TamilLanguageDetector.TAMIL_CHARS.findall(text))
    
    @staticmethod
    def detect_language(text: str) -> Dict[str, any]:
        """
        Comprehensive language detection
        Returns: {
            'language': str,
            'script': str,
            'confidence': float (0-1),
            'tamil_chars': int,
            'english_words': int,
            'details': str
        }
        """
        results = {
            'language': None,
            'script': None,
            'confidence': 0.0,
            'tamil_chars': 0,
            'english_words': 0,
            'mixed_type': None,
            'details': None
        }
        
        # Count Tamil characters
        tamil_count = TamilLanguageDetector.tamil_character_count(text)
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        total_chars = len(text)
        
        results['tamil_chars'] = tamil_count
        results['english_words'] = english_words
        
        # Pure Tamil
        if tamil_count > (total_chars * 0.6):
            results['language'] = 'Tamil'
            results['script'] = 'Tamil Script'
            results['confidence'] = min(tamil_count / total_chars, 1.0)
            results['details'] = f"Pure Tamil with {tamil_count} Tamil characters"
            return results
        
        # Tanglish (Tamil words in English + Tamil mix)
        if tamil_count > 0 and english_words > 0:
            tamil_ratio = tamil_count / total_chars
            if tamil_ratio > 0.2:
                results['language'] = 'Tamil'
                results['script'] = 'Tanglish/Mixed'
                results['confidence'] = 0.85
                results['mixed_type'] = 'Code-mixed (Tamil + English)'
                results['details'] = f"Tanglish detected: {tamil_count} Tamil chars + {english_words} English words"
                return results
        
        # English
        if english_words > (len(text) * 0.3):
            results['language'] = 'English'
            results['script'] = 'Latin'
            results['confidence'] = min(english_words / total_chars, 1.0)
            results['details'] = f"English with {english_words} English words"
            return results
        
        # Default to English if uncertain
        results['language'] = 'English'
        results['script'] = 'Latin'
        results['confidence'] = 0.5
        results['details'] = "Defaulting to English (insufficient signal)"
        
        return results
    
    @staticmethod
    def parse_tamil_content(text: str) -> Dict[str, any]:
        """
        Parse Tamil/Tanglish content and extract meaning
        """
        parsed = {
            'original': text,
            'language': 'Tamil',
            'content_type': None,
            'topics': [],
            'keywords': [],
            'tone': None,
            'target_audience': 'General',
            'script_quality': None,
        }
        
        # Detect content type
        if any(word in text.lower() for word in ['youtube', 'automation', 'earn', 'income', 'passive']):
            parsed['content_type'] = 'Monetization/How-To'
        elif any(word in text.lower() for word in ['tutorial', 'class', 'learn', 'step']):
            parsed['content_type'] = 'Educational'
        else:
            parsed['content_type'] = 'General'
        
        # Extract topics
        if 'youtube' in text.lower() or 'youtube' in text:
            parsed['topics'].append('YouTube')
        if 'automation' in text.lower():
            parsed['topics'].append('Automation')
        if any(word in text.lower() for word in ['passive', 'income', 'earn', 'money']):
            parsed['topics'].append('Monetization')
        
        # Detect tone (based on markers)
        if 'பண்ணுவேன்' in text or 'explain' in text.lower():
            parsed['tone'] = 'Educational/Instructive'
        
        # Evaluate script quality
        tamil_count = TamilLanguageDetector.tamil_character_count(text)
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        
        if tamil_count > (len(text) * 0.7):
            parsed['script_quality'] = 'Good - Pure Tamil'
        elif tamil_count > 0 and english_words > 0:
            parsed['script_quality'] = 'Fair - Tanglish (code-mixed)'
        else:
            parsed['script_quality'] = 'Needs Improvement'
        
        return parsed


class MultiLanguageAnalyzer:
    """
    Multi-language script analyzer that detects and generates content for different languages
    """
    
    SUPPORTED_LANGUAGES = {
        'English': {'code': 'en', 'script': 'Latin', 'region': 'Global'},
        'Tamil': {'code': 'ta', 'script': 'Tamil', 'region': 'South India'},
        'Hindi': {'code': 'hi', 'script': 'Devanagari', 'region': 'North India'},
        'Spanish': {'code': 'es', 'script': 'Latin', 'region': 'Spain/Latin America'},
        'French': {'code': 'fr', 'script': 'Latin', 'region': 'France/Africa'},
        'Portuguese': {'code': 'pt', 'script': 'Latin', 'region': 'Brazil/Portugal'},
    }
    
    @staticmethod
    def get_supported_languages() -> list:
        """Return list of supported languages"""
        return list(MultiLanguageAnalyzer.SUPPORTED_LANGUAGES.keys())
    
    @staticmethod
    def analyze_script(text: str, selected_language: str = None) -> Dict[str, any]:
        """
        Analyze script and generate recommendations
        """
        # First, auto-detect
        detector = TamilLanguageDetector()
        detected = detector.detect_language(text)
        
        # Override with selected language if provided
        if selected_language:
            detected['language'] = selected_language
            detected['user_selected'] = True
        else:
            detected['user_selected'] = False
        
        # Get language details
        lang_details = MultiLanguageAnalyzer.SUPPORTED_LANGUAGES.get(
            detected['language'], 
            MultiLanguageAnalyzer.SUPPORTED_LANGUAGES['English']
        )
        
        # Parse based on language
        if detected['language'] == 'Tamil':
            parsed = TamilLanguageDetector.parse_tamil_content(text)
        else:
            parsed = {'content_type': 'General', 'topics': [], 'tone': 'Neutral'}
        
        return {
            'detected_language': detected['language'],
            'script': detected['script'],
            'confidence': detected['confidence'],
            'language_code': lang_details['code'],
            'language_region': lang_details['region'],
            'parsed_content': parsed,
            'analysis': detected,
        }


# Test the module
if __name__ == "__main__":
    # Test Tamil detection
    tamil_text = "இன்று நான் எப்படி YouTube automation மூலம் passive income earn பண்ணலாம் என்று explain பண்ணுவேன்."
    
    detector = TamilLanguageDetector()
    print("=" * 80)
    print("TAMIL LANGUAGE DETECTION TEST")
    print("=" * 80)
    print(f"\nInput Text: {tamil_text}\n")
    
    # Test 1: Detection
    detection = detector.detect_language(tamil_text)
    print("Detection Result:")
    for key, value in detection.items():
        print(f"  {key}: {value}")
    
    # Test 2: Parsing
    parsed = detector.parse_tamil_content(tamil_text)
    print("\nParsed Content:")
    for key, value in parsed.items():
        print(f"  {key}: {value}")
    
    # Test 3: Multi-language analysis
    analyzer = MultiLanguageAnalyzer()
    print("\nSupported Languages:", analyzer.get_supported_languages())
    
    analysis = analyzer.analyze_script(tamil_text)
    print("\nAnalysis Results:")
    for key, value in analysis.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 80)
