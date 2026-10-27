# MdictLive

[![GitHub Release](https://img.shields.io/github/v/release/nxxxsooo/mdict-live?style=flat-square&color=blue)](https://github.com/nxxxsooo/mdict-live/releases)
[![Docker Pulls](https://img.shields.io/docker/pulls/tardivo/mdict-live?style=flat-square&color=2496ED)](https://hub.docker.com/r/tardivo/mdict-live)
[![License](https://img.shields.io/github/license/nxxxsooo/mdict-live?style=flat-square&color=green)](https://github.com/nxxxsooo/mdict-live/blob/main/LICENSE)
[![Platform](https://img.shields.io/badge/platform-amd64%20%7C%20arm64-8A2BE2?style=flat-square)](https://hub.docker.com/r/tardivo/mdict-live/tags)

MdictLive is a private, self-hosted MDict reader and evidence service. The v2
foundation combines a React reading workspace, a versioned HTTP API, a
standalone CLI, and read-only Pi agent tools over the same local `.mdx` and
`.mdd` corpus.

MdictLive 是面向个人词典库的私有、自托管 MDict 阅读与证据服务。v2
基础版以同一套本地 `.mdx`／`.mdd` 语料同时服务浏览器、CLI 和 Pi 智能体工具。

> v2 is a foundation release. Keep it on localhost, a trusted LAN/VPN, or
> behind an authenticated private reverse proxy. Direct public-Internet
> exposure is unsupported because legacy compatibility routes remain
> unauthenticated during migration.

## What v2 adds

- A continuous reading workspace with source ledger, stable quick sense,
  citations, partial-result states, saved/history panels, and phone navigation.
- Native dictionary presentation inside an opaque sandboxed frame. Useful
  source markup, CSS, media, links, and sound are retained; dictionary scripts,
  inline handlers, unsafe URLs, forms, navigation, popups, and downloads are
  inert. Only the bounded application bridge can request supported actions.
- A bearer-protected `/api/v2` contract for source discovery, bounded lookup,
  suggestions, metadata, citations, service status, and signed resources.
- Stable source identity and revision-aware citations across file moves, with
  explicit `410 Gone` for stale or unsupported evidence.
- A separately installable Python 3.11+ CLI with human, JSON, and bounded agent
  output.
- A Pi package with four read-only tools: sources, lookup, citation resolution,
  and suggestions. Provider credentials and model configuration remain owned by
  the Pi host.
- A non-root Gunicorn container with a read-only corpus, separate persistent
  data/index/config paths, health checks, secret-file tokens, and optional
  Valkey caching.

The source frame is deliberately not recolored by the app's dark theme. This
keeps complex dictionary CSS truthful while the surrounding workspace follows
the selected shell theme.

## Quick start with Compose

Requirements: Docker Compose and a token file containing at least 32 random
bytes.

```bash
mkdir -p library data index config secrets
openssl rand -hex 32 > secrets/mdict-live-token
chmod 600 secrets/mdict-live-token
docker compose up -d --build
curl -fsS http://127.0.0.1:5248/health/ready
```

Put `.mdx` and matching `.mdd` files under `./library`, then open
`http://127.0.0.1:5248/app/`. Enter the bearer token in Settings; the browser
keeps it only for the current tab.

On a native Linux Docker host, ensure `data`, `index`, and `config` are writable
by container UID/GID `1000:1000`. Direct token bind mounts must be readable by
that identity; Compose manages the declared Docker secret separately. The
deployment guide has exact Unraid permissions.

Canonical container paths:

| Path | Access | Purpose |
|---|---|---|
| `/library` | read-only | MDict corpus and optional legacy database for first-start adoption |
| `/data` | read/write | application database and migration state |
| `/data/index` | read/write | generated, disposable indexes |
| `/config` | read/write | non-secret application configuration |
| `/run/secrets/mdict_live_token` | read-only | bearer token file |

See [private deployment](docs/deployment.md) for Docker Run, Nginx Proxy
Manager, Tailscale, ZeroTier, prefix hosting, token rotation, and the legacy
route boundary. See [migration](docs/migration.md) before moving an existing
`/app/content` installation.

## CLI

Install locally without the Flask source tree:

```bash
python3.12 -m pip install ./cli
export MDICT_LIVE_URL=http://127.0.0.1:5248
mdict-live --token-file "$PWD/secrets/mdict-live-token" health --details
mdict-live --token-file "$PWD/secrets/mdict-live-token" sources
mdict-live --token-file "$PWD/secrets/mdict-live-token" lookup right
mdict-live --token-file "$PWD/secrets/mdict-live-token" --json lookup right
```

The CLI supports named TOML profiles, reverse-prefix base URLs, Unicode phrase
queries, explicit POST-only history recording, and exit codes `0` through `7`.
Run `mdict-live --help` for the complete surface.

## Pi bundle

Install the project-local package through Pi's package mechanism:

```bash
PI_TELEMETRY=0 pi install ./pi-package -l --approve
export MDICT_LIVE_URL=http://127.0.0.1:5248
export MDICT_LIVE_TOKEN_FILE="$PWD/secrets/mdict-live-token"
pi
```

The tools never expose raw entry HTML, service credentials, or provider
configuration to the model. They return bounded text evidence, citations,
partial failures, truncation information, and request identifiers.

## API and development

- Browser workspace: `/app/`
- Minimal unauthenticated health: `/health/live`, `/health/ready`
- Authenticated API discovery: `/api/v2`
- OpenAPI contract: [`contracts/openapi-v2.yaml`](contracts/openapi-v2.yaml)
- Agent tool contract: [`contracts/agent-tools-v1.json`](contracts/agent-tools-v1.json)
- Release status: [`docs/release-notes-v2.md`](docs/release-notes-v2.md)

```bash
# Backend tests
cd flask-mdict
python3.12 -m pip install -r requirements-dev.txt
python3.12 -m pytest -q

# Browser workspace
cd ../website
npm ci
npm test
npm run lint
npm run build
```

## Non-goals and known limitations

- MdictLive is not a public multi-user service, hosted model gateway, dictionary
  marketplace, or replacement MDict parser.
- Legacy `/api` and `/mdict` routes are preserved for compatibility and do not
  inherit v2 bearer authentication. Isolate the entire origin.
- First discovery hashes complete MDX/MDD files. Warm lookups are cached, but a
  very large cold corpus can take time to verify.
- Dictionary-authored scripts and inline event handlers are intentionally not
  executed. A rare entry that depends on them can look or behave differently
  from the desktop dictionary application.
- Raycast and generic MCP adapters are downstream work. The CLI and
  runtime-neutral agent contract are the intended integration foundation.
- The image uses one Gunicorn process so the source catalog, cache, and bounded
  lookup executor have a single owner; request concurrency comes from threads.

## Credits

Forked from [liuyug/flask-mdict](https://github.com/liuyug/flask-mdict).
Frontend and v2 foundation by [Mingjian Shao](https://mjshao.fun).

- [Project page](https://mjshao.fun/mdict-live)
- [Docker Hub](https://hub.docker.com/r/tardivo/mdict-live)
- [GitHub](https://github.com/nxxxsooo/mdict-live)
