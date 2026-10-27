# MdictLive v2 verification record

Initial verification: 2026-08-04
Latest release check: 2026-10-08

This record covers the v2 foundation release gate. Commands were run from the
repository root unless a working directory is shown.

## 2026-10-08 release check

The foundation still has all 74 implementation tasks checked. The proposal was
corrected to describe the implemented v2 browser workspace with explicit legacy
fallback; the previous statement that the SPA stayed on legacy APIs was stale.

The dependency audit found 20 frontend findings and 7 Pi development findings.
Compatible lockfile updates cleared the frontend findings. The Pi SDK's exact
`undici@8.5.0` dependency required a scoped `undici@^8.11.2` override in this
package's development installation; `@earendil-works/pi-coding-agent` remains
at `0.83.0`, and this override does not update the user's separately installed
Pi host. Both package audits now report zero known vulnerabilities.

| Surface | Command | Fresh outcome |
|---|---|---|
| Backend | `cd flask-mdict && python -m pytest -q` | 218 passed in 6.49 s |
| CLI | `cd cli && python -m pytest -q` | 12 passed in 13.23 s |
| Browser unit tests | `cd website && npm test` | 14 passed in 935 ms |
| Browser lint | `cd website && npm run lint` | passed |
| Browser production build | `cd website && npm run build` | Vite 7.3.7; 1,764 modules; passed in 1.36 s |
| Headless browser, including real OALD entry | `cd website && MDICT_REAL_ENTRY_HTML="$REAL_ENTRY_HTML" npm run test:e2e` | all 4 passed in 5.1 s |
| Pi tools | `cd pi-package && npm test` | 6 passed in 957 ms |
| Pi types | `cd pi-package && npm run typecheck` | passed |
| Frontend dependency audit | `cd website && npm audit --audit-level=low` | zero vulnerabilities |
| Pi development dependency audit | `cd pi-package && npm audit --audit-level=low` | zero vulnerabilities |

The commands used the same isolated Python test environment as the initial
gate. The real dictionary fixture remained an external local extraction and
was not added to the source repository. Docker and live model/provider
verification below are historical August evidence; they were not repeated in
this October dependency cleanup.

OpenSpec closure: all five capability deltas were synchronized into canonical
specs, preserving every Purpose, requirement, and scenario. The 47 requirements
passed strict validation. The completed change, including its `.openspec.yaml`
metadata and all 74 checked tasks, was archived under
`openspec/changes/archive/2026-10-08-mdict-live-v2-foundation/`. A subsequent
`openspec list --json` returned no active changes; `openspec validate --all
--strict` passed all five canonical specs, and `git diff --check` passed.

## Automated suites

| Surface | Command | Outcome |
|---|---|---|
| Backend unit, contract, migration, compatibility, security | `cd flask-mdict && python -m pytest -q` | 218 passed in 5.04 s |
| Standalone CLI subprocess/install tests | `cd cli && python -m pytest -q` | 12 passed in 15.39 s |
| Browser unit/component tests | `cd website && npm test` | 4 files, 14 tests passed in 839 ms |
| Browser lint | `cd website && npm run lint` | passed, no findings |
| React production build | `cd website && npm run build` | 1,764 modules; JS 271.47 kB, CSS 39.29 kB; passed in 1.05 s |
| Browser real-runtime matrix | `cd website && npm run test:e2e` | 3 passed, 1 real-corpus conditional skipped in 4.0 s |
| Real OALD corpus case | `cd website && MDICT_REAL_ENTRY_HTML="$REAL_ENTRY_HTML" npm run test:e2e -- --grep 'manual real-corpus fixture'` | 1 passed in 3.3 s |
| Pi package | `cd pi-package && npm test` | 3 files, 6 tests passed in 678 ms |
| Pi TypeScript | `cd pi-package && npm run typecheck` | passed |
| OpenSpec | `openspec validate mdict-live-v2-foundation --strict` | valid |
| Compose | `MDICT_LIVE_TOKEN_FILE=/dev/null docker compose config --quiet` | passed |
| Unraid XML | parse `mdict-live.xml` with Python `ElementTree` | passed |
| Patch hygiene | `git diff --check` | passed |

The Pi integration suite includes a real fake-HTTP-service transport. A
separate host workflow invoked `mdict_lookup` through both host-selected
`gpt-5.6-luna` and `claude-sonnet-5`; both returned the same source/block
citation. No provider implementation or credential was added to the package.

## Container and deployment matrix

The local ARM64 production image was built with:

```bash
docker build --progress=plain -t mdict-live:v2-smoke .
```

Result: successful `linux/arm64` image, 84,256,329 bytes. The container ran as
`mdict-live`, used Gunicorn 23 with one `gthread` worker, had a read-only root
filesystem, and became Docker `healthy` through `/health/ready`.

| Route | Exercise | Valid token | Missing token | Invalid token | Result |
|---|---|---:|---:|---:|---|
| Local host port | direct `127.0.0.1` HTTP | 200 | 401 | 401 | passed |
| Private container network | service DNS on an isolated Docker bridge | 200 | 401 | 401 | passed |
| Nginx/NPM-equivalent prefix | `/dictionary/` with prefix strip and `X-Forwarded-Prefix` | 200 | 401 | 401 | passed |

The prefix root returned `302` to `/dictionary/app/`; the workspace and hashed
JS asset both returned `200`; the standalone CLI returned live/ready/service
ready through the prefix. The immediate proxy was restricted to the test
bridge CIDR. An untrusted CORS preflight returned `403` without an
`Access-Control-Allow-Origin` header.

The corpus mount rejected a write probe, while `/data/index` accepted one. The
SQLite database under `/data` remained 73,728 bytes across an exact container
replacement, and the empty read-only library remained unchanged. Starting the
image with an absent token file failed closed before binding.

The repository workflow continues to declare both `linux/amd64` and
`linux/arm64`. Local per-platform builds are the release gate because the
desktop Docker driver cannot export a multi-platform image directly. Both
completed from the same Dockerfile: ARM64 was 84,256,329 bytes and AMD64 was
79,868,006 bytes.

## Representative corpus matrix

Synthetic entries pass backend safe-representation and legacy goldens. Native
browser behavior is then exercised at desktop and 390 px phone widths; the real
OALD extraction is used as the high-complexity integration case.

| Case | Fidelity retained | Security/bridge result | Desktop and phone |
|---|---|---|---|
| Plain | headings, paragraphs, emphasis, ordered visible text | no ambient privilege required | readable; no page overflow |
| CSS-heavy | source selectors, fonts, colors, grid/block layout | workspace CSS and dark theme do not enter the source document | source layout retained at both widths |
| Media-heavy | safe images, fonts, signed resources, sound affordances | source paths become capabilities; sound goes through the typed bridge | media remains source-scoped; bounded fallback available |
| Malformed | browser-recoverable markup and visible text | unsafe URLs, embeddings, handlers, and scripts are inert | remains readable; no workspace failure |
| Link-heavy | MDict entry labels and readable fallbacks | entry changes become validated bridge messages; no frame navigation | deterministic lookup at both widths |
| Table-heavy | table structure and source CSS | overflow stays inside the native document, not the workspace page | table retained; outer page has zero horizontal overflow |
| Script-bearing | non-script markup and CSS | source scripts and inline handlers are removed; only the nonce-bound app bridge runs | stable degraded behavior at both widths |
| Real OALD 10 `right` | 4,000+ tags, 80+ classes, 250+ IDs, one table, 150+ entry actions, 200+ sound actions | zero source scripts, zero inline handlers; entry/sound/full-view bridge paths pass | desktop, dark shell, full source view, and 390 px phone pass with zero console errors |

The quick sense remains outside every native source document. It is derived
deterministically from the first cited visible-text block, falling back to
structured metadata only when required; no model is needed.

## Measured bounds and failure behavior

Command:

```bash
PYTHONPATH=flask-mdict python tools/measure-v2-acceptance.py
```

Measured on the local development machine with deterministic synthetic data:

| Check | Measurement | Result |
|---|---|---|
| Complete hashing | 8,388,595-byte MDX fixture | initial 4.551 ms; repeat full verification 3.776 ms; revision stable |
| Warm lookup cache | one exact entry | cold 0.798 ms; warm 0.038 ms; one source call total |
| Partial source error | one healthy, one failing | returned one evidence entry in 0.386 ms with `source_error` |
| HTML response bound | 10-byte limit | zero partial entries returned; `html_response_bytes` reported |
| Per-source timeout | 5 ms limit against 50 ms fixture | returned `source_timeout` in 6.450 ms |
| Executor saturation | one worker, zero queue | returned deterministic `executor_saturated` in 12.938 ms |
| Cache invalidation | source revision changed | cache key changed; neither key contained the secret |

Timing values are evidence from this run, not service-level guarantees. The
behavioral assertions and complete-entry truncation rules are the durable gate.

## Leak and trust-boundary checks

- Minimal unauthenticated health contains only readiness/liveness state.
- Missing/invalid-token errors are uniform and do not echo the supplied value.
- Authenticated status reports booleans, counts, capabilities, and limits, not
  secret files, host paths, cache credentials, source paths, dictionary names,
  or entry content.
- A seven-artifact runtime scan of health, authentication errors, status, and
  container logs found zero bearer-secret, invalid-probe, or host-path matches.
- Backend tests cover unexpected-error traceback suppression, exact CORS,
  forwarded-header trust, signed-resource forgery/expiry/traversal, and secret
  exclusion from cache keys.
- Browser tests reject forged/wrong-window bridge messages. Pi and CLI tests
  verify bounded plain-text output and exclude raw HTML and transport secrets.

## Environment gaps

The Nginx prefix and Docker private bridge exercise the same HTTP/proxy
contracts used by Nginx Proxy Manager and VPN access, but this run did not
mutate the retired Unraid service or deploy onto the user's real NPM,
Tailscale, or ZeroTier nodes. Those systems remain a deployment-time smoke
check, not a source-code release blocker.
