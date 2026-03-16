"""
Website Name Learning Service — N.A.T. AI Assistant
==================================================
Learns and remembers website names for better responses.
"""
import json
import os
from typing import Dict, Optional
from pathlib import Path

from config import config


class WebsiteNameLearner:
    """
    Learns and remembers website names.
    Example: "chatgpt" → "ChatGPT", "youtube" → "YouTube"
    """
    
    def __init__(self):
        self.learned_names_file = config.BASE_DIR / "database" / "website_names.json"
        self.learned_names: Dict[str, str] = {}
        self._load()
        
        # Default website names (fallback)
        self.default_names = {
            "chat.openai.com": "ChatGPT",
            "chatgpt.com": "ChatGPT",
            "youtube.com": "YouTube",
            "www.youtube.com": "YouTube",
            "google.com": "Google",
            "www.google.com": "Google",
            "github.com": "GitHub",
            "www.github.com": "GitHub",
            "wikipedia.org": "Wikipedia",
            "www.wikipedia.org": "Wikipedia",
            "amazon.com": "Amazon",
            "www.amazon.com": "Amazon",
            "netflix.com": "Netflix",
            "www.netflix.com": "Netflix",
            "twitter.com": "Twitter",
            "x.com": "X (Twitter)",
            "reddit.com": "Reddit",
            "www.reddit.com": "Reddit",
            "stackoverflow.com": "Stack Overflow",
            "spotify.com": "Spotify",
            "open.spotify.com": "Spotify",
            "discord.com": "Discord",
            "whatsapp.com": "WhatsApp",
            "web.whatsapp.com": "WhatsApp",
            "telegram.org": "Telegram",
            "linkedin.com": "LinkedIn",
            "instagram.com": "Instagram",
            "facebook.com": "Facebook",
            "microsoft.com": "Microsoft",
            "apple.com": "Apple",
            "adobe.com": "Adobe",
            "notion.so": "Notion",
            "figma.com": "Figma",
            "slack.com": "Slack",
            "zoom.us": "Zoom",
        }
    
    def _load(self):
        """Load learned names from file."""
        if self.learned_names_file.exists():
            try:
                with open(self.learned_names_file, "r", encoding="utf-8") as f:
                    self.learned_names = json.load(f)
                print(f"[WebsiteLearner] Loaded {len(self.learned_names)} learned names")
            except Exception as e:
                print(f"[WebsiteLearner] Error loading: {e}")
                self.learned_names = {}
    
    def _save(self):
        """Save learned names to file."""
        try:
            os.makedirs(self.learned_names_file.parent, exist_ok=True)
            with open(self.learned_names_file, "w", encoding="utf-8") as f:
                json.dump(self.learned_names, f, indent=2)
        except Exception as e:
            print(f"[WebsiteLearner] Error saving: {e}")
    
    def get_name(self, url: str) -> Optional[str]:
        """Get the learned/nice name for a URL."""
        # Clean the URL
        url = url.lower()
        url = url.replace("https://", "").replace("http://", "").replace("www.", "")
        
        # Remove trailing slash
        url = url.rstrip("/")
        
        # Check learned names first (user corrections)
        if url in self.learned_names:
            return self.learned_names[url]
        
        # Check default names
        if url in self.default_names:
            return self.default_names[url]
        
        # Check partial match (e.g., "chat.openai.com" matches "openai.com")
        for domain, name in self.default_names.items():
            if domain in url or url in domain:
                return name
        
        # Check learned partial matches
        for domain, name in self.learned_names.items():
            if domain in url or url in domain:
                return name
        
        # Extract from domain if no match
        parts = url.split(".")
        if len(parts) >= 2:
            # Return capitalized second-level domain
            name = parts[-2].capitalize()
            # Special cases
            special = {
                "github": "GitHub",
                "youtube": "YouTube",
                "stackoverflow": "Stack Overflow",
                "stackoverflow": "Stack Overflow",
                "linkedin": "LinkedIn",
                "instagram": "Instagram",
                "facebook": "Facebook",
            }
            return special.get(name, name)
        
        return None
    
    def learn_name(self, url: str, name: str):
        """Learn a new website name or correct an existing one."""
        # Clean URL
        clean_url = url.lower()
        clean_url = clean_url.replace("https://", "").replace("http://", "").replace("www.", "")
        clean_url = clean_url.rstrip("/")
        
        self.learned_names[clean_url] = name
        self._save()
        print(f"[WebsiteLearner] Learned: {clean_url} → {name}")
    
    def get_or_extract_name(self, url: str) -> str:
        """Get name or extract from URL."""
        name = self.get_name(url)
        if name:
            return name
        
        # Extract from URL
        url = url.lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
        parts = url.split(".")
        if len(parts) >= 2:
            return parts[-2].capitalize()
        return url.capitalize()


# Global singleton
website_learner = WebsiteNameLearner()
