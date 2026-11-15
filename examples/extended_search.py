"""Extended Search uses its own usage rate. Set your key before running."""

from flashdata_search import SearchClient, export_results

with SearchClient(api_key="your-flashdata-api-key") as client:
    result = client.search("robotics research", extended=True, max_results=100)

export_results([result], "output/extended-search")
print(len(result.videos), "video results")
