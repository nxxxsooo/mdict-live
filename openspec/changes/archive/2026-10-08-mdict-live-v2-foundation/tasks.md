## 1. Contract and Test Foundation

- [x] 1.1 Add a backend development-test dependency set and a project test command that does not change the production image dependency set.
- [x] 1.2 Create fake dictionary source adapters and representative HTML fixtures for plain, CSS-heavy, malformed, media, link, table, and script-bearing entries.
- [x] 1.3 Write `contracts/openapi-v2.yaml` with the response envelope, errors, limits, source records, lookup representations, citations, health, and status routes from the specs.
- [x] 1.4 Add automated schema validation for the OpenAPI document and golden request/response examples.

## 2. Storage, Migration, and Source Identity

- [x] 2.1 Add configuration for distinct library, data, index, and config directories while retaining the legacy content-path fallback.
- [x] 2.2 Move application database initialization behind an explicit schema migration layer and add source-registry and migration-event tables.
- [x] 2.3 Implement transactional adoption of a legacy `flask_mdict.db`, including integrity checks, atomic destination replacement, and failure rollback tests.
- [x] 2.4 Implement full streaming MDX/MDD revision verification for every discovery cycle and tests for unchanged, moved, updated, replaced, and simultaneous identical sources.
- [x] 2.5 Implement source-registry matching, stable opaque `source_id` assignment, duplicate-copy handling, legacy UUID aliases, enabled state, ordering, and unavailable-source reasons.
- [x] 2.6 Redirect generated indexes and derived description data to the writable index/data directories and prove startup performs no corpus writes.
- [x] 2.7 Add migration tests using copies of the current history/settings schema, the wordbook schema, and representative legacy index layouts.

## 3. Entry Representation and Citations

- [x] 3.1 Extract resource rewriting and MDict link resolution from Flask routes into a shared representation service.
- [x] 3.2 Implement safe render HTML that preserves useful markup, CSS, media, sound, and entry links while making scripts, event handlers, unsafe URLs, and unsafe embeddings inert.
- [x] 3.3 Implement ordered visible-text block extraction with whitespace normalization and golden fixture tests.
- [x] 3.4 Implement HMAC-protected opaque entry/block citations with representation versions, encoding, decoding, and revision-aware resolution.
- [x] 3.5 Add citation tests for stable unchanged content, individual text blocks, malformed/forged tokens, missing sources, stale revisions, and unsupported representation versions returning `410 Gone`.
- [x] 3.6 Implement short-lived signed HTML/CSS resource capabilities and harden source-scoped resolution against expiry, forgery, raw/encoded path traversal, unsafe MIME handling, and bearer-token leakage.

## 4. Shared Lookup Services

- [x] 4.1 Define framework-independent domain records for sources, entries, text blocks, metadata, bounds, per-source errors, and lookup results.
- [x] 4.2 Implement source discovery and deterministic source/record ordering through the shared catalog.
- [x] 4.3 Implement NFC-normalized exact single-source and multi-source lookup, explicit disabled-source selection, unknown-source validation, side-effect-free GET, and POST-only history recording.
- [x] 4.4 Apply configurable query, source, entry, text, HTML, and byte bounds and report every truncation cause.
- [x] 4.5 Add bounded per-source execution, exception isolation, all-failed `503`, empty-partial `200`, timeout reporting, and concurrency saturation tests.
- [x] 4.6 Implement deterministic prefix suggestions and explicit bounded typo fallback over headwords only.
- [x] 4.7 Move structured lexical metadata access behind the service layer and keep missing metadata non-fatal.
- [x] 4.8 Version v2 cache keys by source revision, request parameters, representations, and bounds; verify source/state changes cannot return stale aggregate results.

## 5. Private v2 HTTP Boundary

- [x] 5.1 Add request IDs plus uniform v2 success/error envelope helpers and JSON handlers for validation, authentication, not-found, gone, and unexpected errors.
- [x] 5.2 Load bearer and optional signing keys from environment or secret-file configuration, use constant-time comparison, redact secrets, and fail v2 startup on any bind when the bearer token is absent.
- [x] 5.3 Replace reflective CORS behavior for v2 with an exact origin allowlist and test non-browser, allowed-preflight, rejected-origin, and state-change cases.
- [x] 5.4 Make forwarded-header handling opt-in through `MDICT_TRUSTED_PROXY_HOPS` and `MDICT_TRUSTED_PROXY_CIDRS` and test direct spoofing versus trusted reverse-proxy requests.
- [x] 5.5 Add unauthenticated minimal liveness/readiness routes and authenticated redacted service status.
- [x] 5.6 Implement authenticated v2 API discovery and source list/update routes against the shared catalog.
- [x] 5.7 Implement authenticated v2 lookup, suggestion, metadata, and citation routes plus the separate signed asset-capability route against the published OpenAPI contract.
- [x] 5.8 Add Flask contract tests for authentication, validation, Unicode/phrase queries, bounds, empty/partial/truncated results, status codes, headers, and secret/path redaction.

## 6. Legacy Compatibility

- [x] 6.1 Capture golden response fixtures for every legacy endpoint used by the current React SPA before refactoring those routes.
- [x] 6.2 Adapt legacy dictionary listing, lookup, suggestions, metadata, history, wordbook, and cache endpoints to shared services without changing their response shapes.
- [x] 6.3 Capture browser-rendering goldens for representative plain, CSS-heavy, media, link, table, malformed, and script-bearing legacy entries before changing the iframe boundary.
- [x] 6.4 Run backend compatibility tests and the existing React production build after each legacy adapter cutover.

## 7. Browser Reading Workspace

- [x] 7.1 Add a typed browser API adapter for v2 source discovery, lookup, suggestions, metadata, citations, partial failures, source ordering, history, and saved-word operations while retaining an explicit legacy fallback during cutover.
- [x] 7.2 Translate the accepted reference-workspace prototype into React components and shared design tokens for the top search bar, source ledger, continuous reading sheet, native source headers, saved/history panels, and contextual explanation drawer.
- [x] 7.3 Implement a reusable native-entry frame that consumes only safe render HTML, omits `allow-same-origin`, grants no navigation/form/popup/download privileges, and permits scripts only for the application-owned bridge after dictionary scripts are inert.
- [x] 7.4 Implement a typed bridge for bounded height, entry links, sound, and supported media actions with per-render capabilities, expected-window validation, payload validation, and automated forged-message tests.
- [x] 7.5 Preserve source-owned CSS and resource behavior without workspace style or theme injection; implement capability refresh plus a dedicated safe-source view and bounded no-bridge fallback for oversized or degraded entries.
- [x] 7.6 Keep structured quick senses, dataset metadata, citations, and optional contextual agent explanations outside native source documents with explicit evidence labels and deterministic lookup behavior when no agent is configured.
- [x] 7.7 Implement accessible initial, loading, complete, no-match, partial, total-failure, and unavailable-render states plus desktop ledger, phone off-canvas navigation, focus return, reduced motion, and no horizontal page overflow.
- [x] 7.8 Add component and real-browser tests for conflicting source selectors, delayed frame resize, internal link navigation, sound messages, dark shell with light native entries, keyboard navigation, mobile layout, and zero runtime/accessibility console errors.
- [x] 7.9 Run the existing React production build and a manual representative-corpus fidelity/security comparison before making the v2 workspace the default browser route.

## 8. Standalone CLI

- [x] 8.1 Create a separately installable Python 3.11 package and `mdict-live` console entry point with version reporting and no dependency on the Flask source tree.
- [x] 8.2 Implement the specified cross-platform TOML config locations, named-profile schema, and precedence across command flags, environment variables, selected profiles, and defaults.
- [x] 8.3 Implement token resolution from explicit input, environment, or protected file while redacting all diagnostics and URLs.
- [x] 8.4 Implement the version-checking HTTP transport, response-envelope decoding, timeouts, and mapped authentication/transport/compatibility/server errors.
- [x] 8.5 Implement the specified `health`, `sources`, `lookup`, `resolve`, and `suggest` syntax with tokenless minimal health, source filtering, and POST-only explicit history recording.
- [x] 8.6 Implement human, JSON, and bounded agent output with clean streams, handled-error JSON envelopes, explicit error precedence, truncation semantics, and documented exit codes `0` through `7`.
- [x] 8.7 Add subprocess tests covering profiles, Unicode phrases, no match, partial evidence, every error class, redaction, and machine-readable output.
- [x] 8.8 Package and smoke-test the CLI through an isolated install against local and reverse-proxied v2 services.

## 9. Runtime-Neutral Agent Tools and Pi Bundle

- [x] 9.1 Create `contracts/agent-tools-v1.json` for source listing, lookup, citation resolution, and suggestions and validate it against the OpenAPI models.
- [x] 9.2 Create an installable Pi package manifest with a TypeScript extension that registers the four read-only tools.
- [x] 9.3 Implement Pi transport configuration so the service URL/token remain outside tool results and model-visible context.
- [x] 9.4 Add bounded result rendering that preserves citations, truncation, partial failures, and request identifiers without exposing raw HTML.
- [x] 9.5 Write the Pi language-research skill covering multi-source comparison, evidence/inference separation, cited claims, generated-example labels, and insufficient-evidence behavior.
- [x] 9.6 Test the Pi extension against a fake v2 service and verify operation with host-selected sub2api OpenAI-compatible and Anthropic-compatible models without bundling provider code or credentials.
- [x] 9.7 Install the package through Pi's supported local/package mechanism and complete a real source-cited lookup workflow.

## 10. Container and Deployment Migration

- [x] 10.1 Update the Docker image to use read-only `/library`, persistent `/data`, writable `/data/index`, a health check, and secret-file token configuration.
- [x] 10.2 Update Compose with the canonical mounts, token setup, reverse-proxy settings, optional Valkey, and a documented legacy volume-mapping transition.
- [x] 10.3 Update the Unraid XML template for the existing `/mnt/user/media/Dicts/` corpus, separate appdata/index paths, token handling, and health status.
- [x] 10.4 Document local, Nginx Proxy Manager, Tailscale, and ZeroTier access patterns and explicitly warn that legacy routes are trusted-network-only during migration.
- [x] 10.5 Document backup, first-start migration, rollback, token rotation, source identity, citation lifetime, and legacy-data caveats.
- [x] 10.6 Build and smoke-test the production image with a read-only corpus and persistent data/index volumes on the supported architecture available locally.
- [x] 10.7 Verify the existing multi-architecture image workflow still builds both `linux/amd64` and `linux/arm64` targets.

## 11. Acceptance and Release Gate

- [x] 11.1 Run the complete unit, contract, migration, browser, CLI, Pi, and React build suites and record the exact commands and outcomes.
- [x] 11.2 Exercise local, direct private-network, and Nginx Proxy Manager reverse-prefix deployments with valid, missing, and invalid tokens.
- [x] 11.3 Run the manual corpus matrix against representative CSS-heavy, media-heavy, malformed, link-heavy, table-heavy, and script-bearing dictionaries and record native-document fidelity, bridge behavior, and security differences at desktop and phone widths.
- [x] 11.4 Verify response bounds, partial-source failures, cache invalidation, initial hashing, warm lookup latency, and saturated worker behavior with measured fixtures.
- [x] 11.5 Confirm no secrets, host paths, private dictionary names, or entry content leak through unauthenticated health, errors, logs, CORS, status responses, or browser bridge messages.
- [x] 11.6 Update the README and release notes with the v2 foundation status, supported browser/CLI/Pi clients, non-goals, known limitations, and downstream Raycast/MCP work.
