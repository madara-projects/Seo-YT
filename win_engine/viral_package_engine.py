import re
from typing import Dict, Any, List
from win_engine.ai.base_provider import BaseAIProvider

class ViralPackageEngine:
    """Clean engine handling complex viral package generation."""

    def __init__(self, provider: BaseAIProvider):
        self.provider = provider

    def generate(self, script_summary: str) -> Dict[str, Any]:
        titles = self._generate_titles(script_summary)
        hook = self._generate_hook(script_summary)
        thumbnail_text = self._generate_thumbnail_text(script_summary)
        
        best_title = titles[0] if titles else "How to Learn Faster (Step-by-Step Guide)"
        
        return {
            "title": best_title,
            "alt_titles": titles[1:] if len(titles) > 1 else [],
            "hook": hook,
            "thumbnail_text": thumbnail_text
        }

    def _generate_titles(self, script_summary: str) -> List[str]:
        system_msg = "You are a YouTube growth expert. Generate EXACTLY 5 highly clickable YouTube titles under 60 characters. No quotes. No hashtags. Return ONLY a numbered list."
        prompt = f"Rules:\n* Use power words\n* Create curiosity\n* Make it viral\n\nTopic:\n{script_summary[:500]}"
        
        res = self.provider.generate(prompt, system_msg=system_msg, max_tokens=250)
        if not res:
            return []
            
        lines = [line.strip() for line in res.split('\n') if len(line.strip()) > 5]
        return [self._clean_title(t) for t in lines]

    def _generate_hook(self, script_summary: str) -> str:
        system_msg = "You are a viral YouTube scriptwriter."
        prompt = f"Write the first 5 seconds (hook). Pattern interrupt, massive curiosity, extremely fast pacing, max 2 lines. No quotes.\n\nTopic:\n{script_summary[:500]}"
        
        res = self.provider.generate(prompt, system_msg=system_msg, max_tokens=100)
        return res.replace('"', '').strip() if res else "You're doing this WRONG...\nHere's what nobody tells you."

    def _generate_thumbnail_text(self, script_summary: str) -> str:
        system_msg = "You are a YouTube thumbnail expert."
        prompt = f"Write the text for a YouTube thumbnail. 2 to 5 words ONLY. Big emotional impact. No punctuation.\n\nTopic:\n{script_summary[:500]}"
        
        res = self.provider.generate(prompt, system_msg=system_msg, max_tokens=20)
        if res:
            return re.sub(r'[^\w\s]', '', res).upper().strip()
        return "BIG MISTAKE"

    def _clean_title(self, title: str) -> str:
        title = re.sub(r'^(\d+[\.\-\)]|\-|\*)\s*', '', title.strip())
        title = title.replace("\n", "").strip().strip('"\'')
        title = title.replace("**", "").replace("*", "")
        if len(title) > 60:
            title = title[:57] + "..."
        return title