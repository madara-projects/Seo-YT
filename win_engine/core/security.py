"""Security middleware and utilities for the YouTube Win-Engine."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Dict, Any, Optional
import logging
from functools import wraps
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class SecurityManager:
    """Central security management for the application."""

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.rate_limits: Dict[str, list] = defaultdict(list)
        self.suspicious_activity: Dict[str, int] = defaultdict(int)

    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key for storage."""
        return self._hash_string(api_key + self.secret_key)

    def validate_api_key_format(self, api_key: str) -> bool:
        """Validate API key format (basic validation)."""
        if not api_key or len(api_key) < 10:
            return False

        # YouTube API keys typically start with specific patterns
        valid_prefixes = ['AIza', 'AIzaSy']
        return any(api_key.startswith(prefix) for prefix in valid_prefixes)

    def check_rate_limit(self, identifier: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
        """Check if request is within rate limits."""
        current_time = time.time()

        # Clean old requests
        self.rate_limits[identifier] = [
            timestamp for timestamp in self.rate_limits[identifier]
            if current_time - timestamp < window_seconds
        ]

        # Check if under limit
        if len(self.rate_limits[identifier]) >= max_requests:
            self.suspicious_activity[identifier] += 1
            logger.warning(f"Rate limit exceeded for {identifier}")
            return False

        # Add current request
        self.rate_limits[identifier].append(current_time)
        return True

    def sanitize_input(self, text: str, max_length: int = 10000) -> str:
        """Sanitize user input to prevent injection attacks."""
        if not text:
            return ""

        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length] + "..."

        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/']
        for char in dangerous_chars:
            text = text.replace(char, "")

        return text.strip()

    def validate_script_content(self, script: str) -> Dict[str, Any]:
        """Validate script content for security and quality."""
        issues = []

        # Length checks
        if len(script) < 10:
            issues.append("Script too short")
        elif len(script) > 50000:  # 50KB limit
            issues.append("Script too long")

        # Content checks
        suspicious_patterns = [
            r'<script', r'javascript:', r'onclick=', r'onload=',
            r'\\x[0-9a-fA-F]{2}',  # Hex encoded characters
            r'%[0-9a-fA-F]{2}',   # URL encoded characters
        ]

        script_lower = script.lower()
        for pattern in suspicious_patterns:
            if pattern.replace('\\', '').replace('[', '').replace(']', '') in script_lower:
                issues.append(f"Suspicious pattern detected: {pattern}")

        # Check for excessive repetition (potential spam)
        words = script.split()
        if len(words) > 10:
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1

            max_repetition = max(word_counts.values())
            if max_repetition > len(words) * 0.3:  # More than 30% repetition
                issues.append("Excessive word repetition detected")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "length": len(script),
            "word_count": len(words) if 'words' in locals() else 0
        }

    def generate_request_id(self) -> str:
        """Generate unique request ID for tracking."""
        return secrets.token_hex(8)

    def log_security_event(self, event_type: str, details: Dict[str, Any], identifier: str):
        """Log security-related events."""
        logger.warning(f"Security Event: {event_type} | User: {identifier} | Details: {details}")

        # Could integrate with external security monitoring here
        if event_type in ['rate_limit_exceeded', 'suspicious_input']:
            self.suspicious_activity[identifier] += 1

    def _hash_string(self, text: str) -> str:
        """Create SHA-256 hash of string."""
        return hashlib.sha256(text.encode()).hexdigest()


# Global security manager instance
security_manager = SecurityManager()


def require_rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """Decorator to enforce rate limiting on functions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract identifier (could be IP, user ID, etc.)
            identifier = kwargs.get('user_id', 'anonymous')

            if not security_manager.check_rate_limit(identifier, max_requests, window_seconds):
                raise Exception("Rate limit exceeded. Please try again later.")

            return func(*args, **kwargs)
        return wrapper
    return decorator


def validate_input(func):
    """Decorator to validate and sanitize input."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Sanitize script input if present
        if 'script' in kwargs:
            kwargs['script'] = security_manager.sanitize_input(kwargs['script'])

        # Validate script content
        if 'script' in kwargs:
            validation = security_manager.validate_script_content(kwargs['script'])
            if not validation['valid']:
                raise ValueError(f"Invalid script content: {', '.join(validation['issues'])}")

        return func(*args, **kwargs)
    return wrapper