"""Run after setting the key; rerun with resume=True to use completed searches."""

from flashdata_search import SearchClient, collect

with SearchClient(api_key="your-flashdata-api-key") as client:
    summary = collect(
        client,
        ["battery recycling process", "lithium battery recycling plant"],
        "output/battery-recycling",
        max_results=20,
        filters={"type": "video", "duration": "4-20", "subtitles": True},
    )

print(summary["unique_videos"], "videos ready for review")
