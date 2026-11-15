"""Run: python examples/search.py (set your key below first)."""

from flashdata_search import SearchClient, export_results

with SearchClient(api_key="your-flashdata-api-key") as client:
    result = client.search("battery recycling process", max_results=5)

for video in result.videos:
    print(video["title"], video["url"])

export_results([result], "output/one-search")
