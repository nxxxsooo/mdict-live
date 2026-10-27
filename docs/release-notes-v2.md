# MdictLive v2 foundation release notes

Status: foundation implementation and local release-candidate validation
complete. Publication and live home-infrastructure cutover remain explicit
operator actions.

The `mdict-live-v2-foundation` change was archived on 2026-10-08 with all 74
tasks complete. Its 47 requirements now live in the five canonical specs under
[`openspec/specs/`](../openspec/specs/). The archived proposal, design, deltas,
and task evidence are retained under
[`2026-10-08-mdict-live-v2-foundation`](../openspec/changes/archive/2026-10-08-mdict-live-v2-foundation/).

Release check repeated on 2026-10-08: backend, CLI, frontend, headless real-entry
browser checks, and Pi tests/types pass. Compatible dependency updates and a
scoped Pi development SDK override clear both npm audits. See
[verification-v2.md](verification-v2.md) for fresh results and historical
deployment evidence.

## Included

- Versioned, bearer-protected `/api/v2` contract with bounded lookup,
  suggestions, metadata, revision-aware citations, signed assets, source
  management, health, and redacted status.
- Stable source registry and transactional adoption of the legacy SQLite
  database into the separated `/data` layout.
- Safe native dictionary representation: source markup, CSS, media, sound, and
  entry links survive where safe; scripts, inline handlers, dangerous URLs, and
  ambient browser privileges do not.
- React reading workspace with source ledger, stable quick sense outside the
  source frame, citations, partial/failure states, source-native full view,
  saved/history panels, responsive navigation, and accessible focus behavior.
- Separately installable Python 3.11+ CLI with human, JSON, and bounded agent
  output.
- Runtime-neutral agent tool contract and a Pi reference package with four
  read-only, citation-preserving tools.
- Non-root Gunicorn image, read-only root/corpus support, persistent data and
  index mounts, secret-file configuration, readiness health check, optional
  Valkey, and updated Compose/Unraid deployment surfaces.

## Compatibility

The current legacy browser/API shapes remain available while they are adapted
to shared services. They remain unauthenticated and are trusted-network-only.
The old `/app/content` volume layout is supported only through the documented
one-release migration path; the canonical v2 corpus mount is `/library:ro`.

## Security and fidelity boundary

MdictLive preserves dictionary-owned presentation, not dictionary-owned code.
The source document has an opaque origin and no forms, navigation, popups,
downloads, or same-origin capability. The application-owned bridge accepts only
validated, capability-bound resize, entry-link, sound, and supported-media
messages. Source documents are not recolored or restyled by the workspace.

## Known limitations

- Direct public-Internet exposure is unsupported.
- Full-corpus verification makes first discovery more expensive than warm
  lookups.
- Entries that require their original JavaScript can degrade because source
  scripts and handlers are intentionally inert.
- The browser token is tab-scoped rather than a multi-user identity session.
- Raycast and generic MCP adapters are not part of this release. They should
  consume the standalone CLI or `contracts/agent-tools-v1.json` in a later
  change.
- Model-provider and BYOK configuration are not bundled; Pi continues to own
  the selected OpenAI-compatible or Anthropic-compatible provider.

## Upgrade

Read [migration.md](migration.md) before first v2 startup and
[deployment.md](deployment.md) before exposing the service through a VPN or
reverse proxy. Back up the legacy database, mount the corpus read-only, and use
a token file containing at least 32 random bytes.
