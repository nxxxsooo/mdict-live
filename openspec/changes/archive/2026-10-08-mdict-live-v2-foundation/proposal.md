## Why

MdictLive already reads the existing MDict corpus well, but its current API and storage model are coupled to the browser UI and are not safe or stable enough for CLI, Raycast, MCP, or agent clients. The dormant project can become useful again by turning that proven parser into a private, versioned dictionary service without making AI a runtime dependency.

## What Changes

- Introduce a versioned `/api/v2` contract for source discovery, bounded multi-source lookup, suggestions, metadata, and health information.
- Return both faithful dictionary HTML and extracted plain text, with stable source identities and citation anchors suitable for humans and machines.
- Preserve each lexicon's source-owned HTML and CSS inside an opaque-origin browser boundary instead of normalizing arbitrary entries into one application stylesheet.
- Add token-based programmatic access, explicit CORS policy, reverse-proxy-safe behavior, and predictable JSON errors while keeping the product single-user.
- Separate the read-only dictionary corpus from writable application data and generated indexes, with migration support for the current content layout.
- Add a standalone CLI that can use local or remote MdictLive profiles and emit readable, JSON, or agent-oriented output.
- Define a runtime-neutral agent tool contract and ship Pi as the first reference bundle; model providers and BYOK credentials remain outside the deterministic core.
- Preserve the existing `/api` and browser behavior during migration until compatibility and entry-rendering checks pass.
- Migrate the browser workspace to the v2 API with an explicit legacy fallback, and require the entire transitional service to remain behind a private network boundary.

### Non-goals

- Rebuilding the MDict parser or replacing Flask, SQLite, React, or Docker.
- Adding multi-user accounts, public registration, direct public-Internet exposure, cloud synchronization, or a hosted SaaS control plane.
- Making Pi, sub2api, an MCP host, or any language model required for ordinary lookup.
- Building definition-body full-text search in the first milestone.
- Building a full source-administration console, Raycast interface, or standalone MCP distribution in this change; the accepted browser reading workspace and native-entry isolation boundary are included.

## Capabilities

### New Capabilities

- `dictionary-api`: Versioned source discovery, lookup, suggestions, metadata, dual representations, stable citations, bounds, and compatibility behavior.
- `dictionary-web`: Responsive private reading workspace, source-faithful native entry documents, opaque-origin isolation, typed frame interactions, and separation of deterministic evidence from agent guidance.
- `private-service`: Single-user authentication, origin and proxy controls, storage separation, health reporting, and safe self-hosted operation.
- `dictionary-cli`: Profile-based local or remote lookup with human, JSON, and agent-oriented output and deterministic exit behavior.
- `agent-tooling`: Runtime-neutral dictionary tools plus an optional Pi reference package that can perform source-cited agentic language research.

### Modified Capabilities

None. The repository has no existing OpenSpec capability specifications; legacy behavior remains available during the transition.

## Impact

- Backend: `flask-mdict/app.py`, `flask_mdict/api.py`, lookup helpers, configuration, persistence, and cache keys.
- Browser: the current React reader, its native-entry iframe boundary and application-owned message bridge, the accepted reference-workspace implementation, and representative fidelity fixtures.
- Deployment: Docker image, Compose and Unraid templates, corpus/data/index mounts, environment variables, and reverse-proxy documentation.
- Clients: the migrated browser reader, a standalone CLI, and a Pi package; future Raycast and MCP clients consume the same API.
- Dependencies: one robust HTML-to-text extraction strategy and client packaging dependencies may be added only after compatibility checks.
- Operations: existing installations require a non-destructive data/index migration path and explicit token provisioning for programmatic clients.
