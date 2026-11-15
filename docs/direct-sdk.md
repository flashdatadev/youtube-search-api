# Use the FlashData SDK directly

```bash
python -m pip install "flashdata>=1.2.0,<2"
```

```python
from flashdata import FlashData

with FlashData(api_key="your-flashdata-api-key") as client:
    response = client.youtube.search(
        "battery recycling process",
        max_results=5,
        filters={"type": "video"},
    )

for page in response["results"]:
    for video in page["results"]:
        print(video["videoId"], video["title"])
```

Change the method to `client.youtube.search_extended(...)` and request up to 700 results for Extended Search. It uses a separate source permission and usage rate. Use the toolkit when you also want multi-query collection, exports and completed-query checkpoints.

[API reference](https://flashdata.dev/docs/sources/youtube_search) · [Python SDK](https://github.com/flashdatadev/flashdata-python)
