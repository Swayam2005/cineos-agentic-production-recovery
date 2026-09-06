# CineOS — Autonomous Production Recovery

CineOS is an agentic production-recovery control room for film and television.

## Vertical slice
Producer incident -> Gemini + Google ADK multi-agent analysis -> production tools -> Grafana MCP -> ranked recovery plan.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
gcloud auth application-default login
adk web agents
```

Ask:
> Actor Maya Chen is unavailable for Scene 42 tomorrow. Recover production and explain the safest plan.

## Hackathon compliance
Google Cloud AI/ADK is the AI layer. Grafana is an active runtime integration through MCP. Do not add prohibited AI providers.
