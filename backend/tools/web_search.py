"""
Web Search Tool
Real-time web search for chess-related information using Tavily API
"""

import os
import aiohttp
from typing import Dict, List, Optional, Literal


async def web_search(
    query: str,
    max_results: int = 5,
    search_filter: Literal["all", "news", "games", "players"] = "all",
    include_domains: List[str] = None,
    exclude_domains: List[str] = None
) -> Dict:
    """
    Search the web for chess-related information.
    
    Args:
        query: Search query string
        max_results: Maximum number of results (1-10)
        search_filter: Filter type - all, news, games, players
        include_domains: List of domains to prioritize
        exclude_domains: List of domains to exclude
        
    Returns:
        {
            "results": [{"title": str, "url": str, "snippet": str, "score": float}],
            "news_context": str,  # Summarized context from results
            "query": str,
            "total_results": int
        }
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    
    if not api_key:
        # Fallback: return a message that web search is not configured
        return {
            "results": [],
            "news_context": "Web search not available - TAVILY_API_KEY not configured",
            "query": query,
            "total_results": 0,
            "error": "API key not configured"
        }
    
    # Build domain filters based on search type
    if include_domains is None:
        include_domains = []
    if exclude_domains is None:
        exclude_domains = []
    
    # Add chess-specific domains based on filter
    if search_filter == "news":
        include_domains.extend([
            "chess.com/news",
            "lichess.org/blog", 
            "chess24.com",
            "chessbase.com"
        ])
    elif search_filter == "games":
        include_domains.extend([
            "chessgames.com",
            "chess.com",
            "lichess.org"
        ])
    elif search_filter == "players":
        include_domains.extend([
            "ratings.fide.com",
            "2700chess.com",
            "chess.com/players"
        ])
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.tavily.com/search"
            
            payload = {
                "api_key": api_key,
                "query": f"chess {query}",  # Prefix with chess for relevance
                "max_results": min(max_results, 10),
                "include_answer": True,
                "include_raw_content": False,
                "search_depth": "advanced"
            }
            
            if include_domains:
                payload["include_domains"] = include_domains[:5]  # Tavily limit
            if exclude_domains:
                payload["exclude_domains"] = exclude_domains[:5]
            
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return {
                        "results": [],
                        "news_context": f"Search failed: {error_text}",
                        "query": query,
                        "total_results": 0,
                        "error": f"API error: {response.status}"
                    }
                
                data = await response.json()
                
                # Parse results
                results = []
                for item in data.get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", "")[:500],
                        "score": item.get("score", 0.0)
                    })
                
                # Build news context summary
                news_context = data.get("answer", "")
                if not news_context and results:
                    # Build from snippets
                    snippets = [r["snippet"] for r in results[:3]]
                    news_context = " ".join(snippets)[:1000]
                
                return {
                    "results": results,
                    "news_context": news_context,
                    "query": query,
                    "total_results": len(results)
                }
    
    except Exception as e:
        return {
            "results": [],
            "news_context": f"Search error: {str(e)}",
            "query": query,
            "total_results": 0,
            "error": str(e)
        }


# Tool schema for LLM
TOOL_WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for chess-related information including player news, tournament results, and historical data. Use for real-time information not available in training data.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'Magnus Carlsen 2024 tournaments', 'Hans Niemann cheating allegations')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (1-10)",
                    "default": 5
                },
                "search_filter": {
                    "type": "string",
                    "enum": ["all", "news", "games", "players"],
                    "description": "Filter results by type",
                    "default": "all"
                }
            },
            "required": ["query"]
        }
    }
}

