# Sahaay Core Backend

Authoritative backend orchestrator for Sahaay, an installed voice-first Windows desktop AI agent.

## Components
- **API v1**: Health, Capabilities, Sessions, Tasks, Actions, Sources, Audit
- **Policy Engine**: Deterministic Action Gate
- **Privacy Gateway**: Fail-closed data minimization checkpoint
- **Task Orchestrator**: State machine governing task lifecycle
- **Persistence**: SQLite with async SQLAlchemy & migrations
- **Verification Engine**: Independent verification preserving the invariant that models cannot self-verify
