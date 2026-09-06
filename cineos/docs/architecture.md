# CineOS architecture

Google ADK orchestrates Gemini specialist agents. The recovery agent receives Grafana MCP tools over Streamable HTTP.

For a production deployment we prefer the official `mcp-grafana` server connected to Grafana Cloud, deployed as a private/secured service. This avoids embedding a browser OAuth flow in Agent Engine while still using the official Grafana MCP implementation.

Secrets must be stored in Google Cloud Secret Manager for deployment; `.env` is for local development only.
