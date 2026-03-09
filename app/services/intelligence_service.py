import json
import re
import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

from config import config
from app.services.groq_service import groq_service
from app.services.vector_store import vector_store_service

class IntelligenceService:
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = 3600  # 1 hour

        self.tavily = None
        if TAVILY_AVAILABLE and getattr(config, 'TAVILY_API_KEY', None):
            try:
                self.tavily = TavilyClient(api_key=config.TAVILY_API_KEY)
            except Exception as e:
                print(f"[Intelligence] Tavily error: {e}")

        self.alpha_vantage_key = getattr(config, 'ALPHA_VANTAGE_KEY', '')
        self.fmp_key = getattr(config, 'FMP_KEY', '')
        self.news_api_key = getattr(config, 'NEWS_API_KEY', '')
        self.google_api_key = getattr(config, 'GOOGLE_API_KEY', '')
        self.google_cse_id = getattr(config, 'GOOGLE_CSE_ID', '')
        self.serpapi_key = getattr(config, 'SERPAPI_KEY', '')

    def _cached(self, key: str) -> Optional[Dict]:
        entry = self.cache.get(key.lower().strip())
        if entry and (time.time() - entry['ts']) < self.cache_ttl:
            return entry['data']
        return None

    def _cache(self, key: str, data: Dict):
        self.cache[key.lower().strip()] = {'data': data, 'ts': time.time()}

    def _tavily_search(self, query: str, n: int = 5) -> List[Dict]:
        if not self.tavily:
            return []
        try:
            res = self.tavily.search(query=query, max_results=n)
            return [{'title': r.get('title', ''), 'url': r.get('url', ''),
                     'content': r.get('content', '')[:800], 'source': 'tavily'}
                    for r in res.get('results', [])]
        except Exception:
            return []

    def classify_input(self, user_input: str) -> Dict:
        return {
            "entity_type": "company", "name": user_input,
            "industry": "Unknown", "sector": "Unknown",
            "country": "India", "is_listed": False,
            "stock_symbol": None, "exchange": None,
            "description": user_input
        }

    def fetch_all_data(self, classification: Dict) -> Dict:
        return {'api_data': {}, 'web_data': {}, 'news_data': []}

    def analyze_with_groq(self, classification: Dict, all_data: Dict) -> Dict:
        return {"error": "Analysis bypass", "name": classification.get('name')}

    def format_response(self, classification: Dict, analysis: Dict, query: str) -> str:
        prompt = f"Provide a brief business intelligence summary for {query}."
        try:
            return groq_service.chat([{"role": "user", "content": prompt}])
        except Exception as e:
            return f"Error formatting response: {str(e)}"

    def save_to_memory(self, query: str, classification: Dict, analysis: Dict):
        pass

    def analyze(self, user_query: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        cached = self._cached(user_query)
        if cached:
            return cached

        classification = self.classify_input(user_query)
        all_data = self.fetch_all_data(classification)
        analysis = self.analyze_with_groq(classification, all_data)
        formatted = self.format_response(classification, analysis, user_query)
        self.save_to_memory(user_query, classification, analysis)

        result = {
            "response": formatted,
            "classification": classification,
            "structured_data": analysis,
            "sources_searched": 0,
            "api_sources_used": [],
            "cached": False,
            "entity_name": classification.get('name', user_query),
            "entity_type": classification.get('entity_type', 'company'),
        }

        self._cache(user_query, result)
        return result

intelligence_service = IntelligenceService()