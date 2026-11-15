"""YouTube search and video discovery with FlashData."""

from .search import SearchClient, SearchResult, collect, export_results, read_queries

__all__ = ["SearchClient", "SearchResult", "collect", "export_results", "read_queries"]
