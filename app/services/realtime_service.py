from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

from config import config
from app.services.groq_service import groq_service
from app.services.vector_store import vector_store_service
from app.services.memory_service import memory_service

class RealtimeService:
    def __init__(self):
        self.tavily_client = None
        if TAVILY_AVAILABLE and getattr(config, 'TAVILY_API_KEY', None):
            try:
                self.tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)
                print("[Realtime] Tavily initialized successfully.")
            except Exception as e:
                print(f"[Realtime] Tavily initialization error: {e}")
    
    def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Searches the web using Tavily."""
        results = []
        if self.tavily_client:
            try:
                search_results = self.tavily_client.search(query=query, max_results=max_results)
                for result in search_results.get("results", []):
                    results.append({
                        "title": result.get("title", ""), 
                        "url": result.get("url", ""), 
                        "content": result.get("content", "")[:500], 
                        "source": "tavily"
                    })
                return results
            except Exception as e:
                print(f"[Realtime] Tavily search error: {e}")
        print("[Realtime] Using fallback search mode (No search available)")
        return results

    def _build_system_prompt(self, context: str, search_results: List[Dict[str, str]]) -> str:
        """Builds the comprehensive system prompt including web results and memory."""
        search_context = ""
        if search_results:
            search_context = "\n\nRECENT WEB SEARCH RESULTS:\n"
            for i, result in enumerate(search_results, 1):
                search_context += f"\n{i}. {result['title']}\n   {result.get('content', '')[:300]}...\n   Source: {result['url']}\n"
        
        assistant_name = getattr(config, 'ASSISTANT_NAME', 'Natasha')
        persistent_memory = memory_service.get_system_prompt_context()
        
        prompt = f"""You are {assistant_name}, an advanced AI assistant. Your full name is Natasha, equipped with real-time web search capabilities.

CURRENT TIME: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

USER'S INFO (from memory):
{context}
"""
        
        if persistent_memory:
            prompt += f"""{persistent_memory}
"""
        
        prompt += f"""{search_context}

Guidelines:
- Use the persistent memories above to personalize your responses to the user
- Use the web search results above to provide current, accurate information.
- Cite your sources when referring to the search results.
- Be helpful, concise, and friendly.
- Always remember the user's name, preferences, and important details they told you
- If you do not know the answer, state so honestly."""
        
        return prompt

    def chat(self, message: str, conversation_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Standard non-streaming chat with real-time web search."""
        print(f"[Realtime] Processing: {message[:50]}...")
        
        context = vector_store_service.get_relevant_context(message)
        search_results = self.search_web(message)
        
        system_prompt = self._build_system_prompt(context, search_results)
        messages = conversation_history.copy() if conversation_history else []
        messages.append({"role": "user", "content": message})
        
        try:
            response = groq_service.chat(messages, system_prompt)
            return {"response": response, "sources": search_results, "search_used": len(search_results) > 0}
        except Exception as e:
            print(f"[Realtime] Error: {e}")
            return {"response": f"I apologize, but I encountered an error: {str(e)}", "sources": [], "search_used": False}

    async def stream_chat(self, message: str, conversation_history: List[Dict[str, str]] = None) -> Iterator[str]:
        """Streaming chat with real-time web search integration."""
        print(f"[Realtime Stream] Processing: {message[:50]}...")
        
        # In a real async environment we would await but vector_store_service FAISS call is synchronous. 
        # But we'll leave it as is for now or use asyncio.to_thread in main.
        context = vector_store_service.get_relevant_context(message)
        search_results = self.search_web(message)
        
        system_prompt = self._build_system_prompt(context, search_results)
        messages = conversation_history.copy() if conversation_history else []
        messages.append({"role": "user", "content": message})
        
        try:
            # Yield tokens one by one from groq_service.stream_chat asynchronously
            async for chunk in groq_service.stream_chat(messages, system_prompt):
                yield chunk
        except Exception as e:
            print(f"[Realtime Stream] Error: {e}")
            yield f" I apologize, but I encountered an error: {str(e)}"
    
    def is_available(self) -> bool:
        """Checks if Tavily search is configured and available."""
        return self.tavily_client is not None

realtime_service = RealtimeService()