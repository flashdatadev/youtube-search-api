# Maintenance

- Keep the toolkit Python-only and build on the official FlashData SDK.
- Show placeholder API keys directly in Python in quickstarts. Environment variables are optional.
- Standard Search accepts up to 20 results; Extended Search accepts up to 700 and has a separate usage rate. Never silently switch sources.
- Preserve query provenance and result position when deduplicating videos.
- Never save API keys or authorization headers in exports or checkpoints.
- Retry only explicit 429 responses, with bounded attempts and Retry-After. Do not automatically repeat an uncertain submission.
- Default demos and tests are offline. Label replayed responses with their provenance; never describe fixtures as a fresh live run.
- Run pytest, Ruff, package build, wheel installation and the replay demo before publishing.
