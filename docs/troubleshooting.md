# Search errors and recovery

| Outcome | Action |
| --- | --- |
| HTTP `401` | Check the FlashData API key. Google API keys cannot authenticate FlashData requests. |
| HTTP `403` | Check the key's `youtube_search` or `youtube_search_extended` permission. |
| HTTP `402` | Check account credits. Resume after adding credits. |
| HTTP `429` | The client respects `Retry-After`, with at most two retries by default. Delays above 60 seconds are returned to you for a later retry. |
| Timeout, connection loss or HTTP `5xx` | The request may have been accepted. Check console History. The toolkit does not automatically resubmit it. |
| Empty results | A completed response can contain an empty result list. Try a broader query or remove filters in a new run. |
| `max_results` validation error | Standard supports 1–20; use `extended=True` explicitly for 1–700. |
| Resume configuration mismatch | Reuse the exact original queries, filters, source and limits, or choose a new output folder. |
| Missing video IDs | Non-video or malformed items are counted in `skipped_items`. Raw responses remain in `responses/`. |

`run.json` records whether the full collection completed. If a later query fails, the earlier completed responses and their exports remain available. A response saved just before an interruption is reused on resume. An `uncertain` request without a response file stops resume so it cannot silently charge for a duplicate query. Inspect the corresponding request in console History, then use a new output folder for the remaining queries if you decide to resubmit.

`export_results()` writes the named export files again. Use separate folders for separate collections, and keep manually selected IDs in a different file. Do not run two collectors against the same output directory at the same time.

CSV cells beginning with spreadsheet formula characters are escaped. JSONL retains original values and nulls. `totalResults` is the response count, not the total size of YouTube's index. Retrieval position is the order observed in this query, not a universal rank across users or regions.

[Request history](https://flashdata.dev/app/jobs) · [API errors](https://flashdata.dev/docs/errors) · [Contact support](https://flashdata.dev/contact)
