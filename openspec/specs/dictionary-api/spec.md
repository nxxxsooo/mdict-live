# dictionary-api Specification

## Purpose

Defines a stable, bounded, source-attributed dictionary contract that serves faithful human rendering and machine-readable evidence without requiring an AI runtime.

## Requirements

### Requirement: Versioned API discovery
The service SHALL expose a discoverable `/api/v2` contract and SHALL identify the API version in every successful v2 response.

#### Scenario: Client discovers the API
- **WHEN** an authenticated client requests the v2 API root
- **THEN** the service returns the API version and links to source, lookup, suggestion, metadata, and status resources

#### Scenario: Client requests an unknown v2 route
- **WHEN** a client requests a route that is not part of the v2 contract
- **THEN** the service returns a JSON error with HTTP 404 rather than an HTML error page

### Requirement: Stable dictionary source identity
The service SHALL assign each dictionary an opaque `source_id` and content `revision` that do not depend on its absolute filesystem path.

#### Scenario: Unchanged dictionary moves to another mount path
- **WHEN** the same dictionary content is discovered at a different absolute path
- **THEN** the service reports the same `source_id` and `revision`

#### Scenario: Dictionary content is replaced
- **WHEN** the bytes that define a dictionary change
- **THEN** the service reports a different `revision` so citations cannot silently resolve to changed content

#### Scenario: Identical copies are simultaneously present
- **WHEN** two byte-identical dictionaries are present at distinct paths during the same discovery scan
- **THEN** the service reports two distinct `source_id` values with the same content `revision`

### Requirement: Source discovery
The service SHALL let clients enumerate dictionary sources with their identity, revision, title, enabled state, supported representations, and availability.

#### Scenario: Sources are available
- **WHEN** a client lists sources
- **THEN** the response returns sources in the configured order without exposing host filesystem paths

#### Scenario: A source failed to initialize
- **WHEN** a configured dictionary cannot be opened or indexed
- **THEN** source discovery reports it as unavailable with a stable machine-readable reason while other sources remain usable

### Requirement: Bounded lexical lookup
The service SHALL accept Unicode words or phrases through a query parameter or JSON request body, normalize them to NFC after trimming surrounding Unicode whitespace without removing internal punctuation, and SHALL support optional source selection, representation selection, and result limits.

#### Scenario: Exact lookup succeeds across enabled sources
- **WHEN** a client submits a valid query without selecting sources
- **THEN** the service searches enabled sources and returns matching entries in configured source order

#### Scenario: Client selects sources
- **WHEN** a client supplies one or more valid `source_id` values
- **THEN** the service searches only those sources and reports the applied selection

#### Scenario: Client explicitly selects a disabled source
- **WHEN** a valid but disabled `source_id` is explicitly selected
- **THEN** the service searches it because enablement controls default inclusion rather than direct access

#### Scenario: Client selects an unknown source
- **WHEN** any selected `source_id` is unknown
- **THEN** the service rejects the request with HTTP 422 and identifies the unknown values

#### Scenario: Query exceeds the accepted bound
- **WHEN** a query exceeds 256 Unicode scalar values after trimming
- **THEN** the service rejects it with HTTP 422 and a field-specific error

#### Scenario: Result limit exceeds the server maximum
- **WHEN** a client asks for more results than the configured maximum
- **THEN** the service applies the maximum and reports that the response was bounded

### Requirement: Dual entry representation
Each lookup result SHALL be able to include faithful renderable HTML and extracted plain-text blocks derived from the same dictionary record.

#### Scenario: Client requests both representations
- **WHEN** a client requests `html` and `text`
- **THEN** each entry returns renderable HTML, ordered text blocks, and the same source and revision identity

#### Scenario: Client requests text only
- **WHEN** a client requests only `text`
- **THEN** the response omits dictionary HTML and resource payloads

#### Scenario: Entry contains scripts or styling metadata
- **WHEN** plain text is extracted from dictionary markup
- **THEN** scripts, styles, and non-content metadata are excluded while meaningful reading order and visible text are preserved

### Requirement: Stable citation anchors
Every returned entry and text block SHALL include an opaque citation URI that identifies the source, revision, representation-pipeline version, entry, and block without containing a host filesystem path.

#### Scenario: Citation is resolved against unchanged content
- **WHEN** a client resolves a citation whose source revision is still available
- **THEN** the service returns the cited entry or block and its current source metadata

#### Scenario: Citation revision is no longer available
- **WHEN** a client resolves a citation for content that has been replaced or removed
- **THEN** the service returns HTTP 410 with the unavailable source and revision identifiers

#### Scenario: Citation uses an unsupported representation version
- **WHEN** a citation requires an extraction/normalization version the service no longer supports
- **THEN** the service returns HTTP 410 without silently resolving it through a different pipeline

### Requirement: Deterministic ordering and partial results
Lookup responses SHALL use deterministic source and record ordering and SHALL distinguish complete, partial, truncated, and empty results.

#### Scenario: One source fails during multi-source lookup
- **WHEN** at least one selected source succeeds and another times out or fails
- **THEN** the service returns successful entries with `partial: true` and a per-source error summary

#### Scenario: No source contains the query
- **WHEN** all selected sources complete without a match
- **THEN** the service returns HTTP 200 with an empty entry list and `partial: false`

#### Scenario: Some sources fail and successful sources have no match
- **WHEN** at least one selected source completes without a match and another source fails
- **THEN** the service returns HTTP 200 with an empty entry list, `partial: true`, and the per-source error summary

#### Scenario: Every selected source fails
- **WHEN** no selected source completes successfully
- **THEN** the service returns HTTP 503 with a structured per-source failure summary

#### Scenario: Payload bound is reached
- **WHEN** the response reaches a configured entry, text, or byte bound
- **THEN** the service stops at the last complete entry or text block and reports which bound caused truncation and which sources may be queried more narrowly

### Requirement: Suggestions and typo fallback
The service SHALL provide prefix suggestions and SHALL support an explicitly requested typo-tolerant fallback over dictionary headwords without searching definition bodies.

#### Scenario: Prefix suggestions are requested
- **WHEN** a client submits a non-empty prefix
- **THEN** the service returns a bounded, deduplicated list in deterministic order

#### Scenario: Typo fallback is requested after no exact match
- **WHEN** exact lookup has no result and the client requests fuzzy fallback
- **THEN** the service returns ranked headword candidates marked as suggestions rather than definitions

### Requirement: Structured lexical metadata
The service SHALL return available phonetic, frequency, tag, inflection, definition, and translation metadata separately from dictionary entry markup and SHALL identify the metadata dataset rather than merge it with MDict evidence.

#### Scenario: Metadata exists
- **WHEN** a client requests metadata for a known word
- **THEN** the response returns present fields with their source and omits unavailable optional fields

#### Scenario: Metadata database is unavailable
- **WHEN** the optional metadata database is not configured
- **THEN** the service reports the capability as unavailable without failing dictionary lookup

### Requirement: Lookup side effects are explicit
Programmatic v2 GET lookup SHALL always be side-effect free. A v2 POST lookup SHALL NOT change search history unless the authenticated client explicitly requests history recording.

#### Scenario: CLI performs an ordinary lookup
- **WHEN** a client performs lookup without `record_history`
- **THEN** the service does not create or increment a history record

#### Scenario: Trusted client records history
- **WHEN** a client performs POST lookup with `record_history: true`
- **THEN** the service records the normalized query once after at least one source matches

#### Scenario: GET includes a history parameter
- **WHEN** a client adds `record_history` to a GET lookup
- **THEN** the service rejects the unsupported parameter and leaves history unchanged

### Requirement: Predictable error envelope
Every v2 error SHALL use a JSON envelope containing a stable error code, human-readable message, request identifier, and optional structured details.

#### Scenario: Request validation fails
- **WHEN** one or more request fields are invalid
- **THEN** the response uses HTTP 422 and identifies each invalid field in `details`

#### Scenario: Unexpected server failure occurs
- **WHEN** the service cannot safely complete a request
- **THEN** it returns HTTP 500 with a request identifier and does not expose paths, secrets, or a Python traceback

### Requirement: Legacy API transition
The service SHALL preserve existing unversioned API and browser routes during the v2 foundation rollout.

#### Scenario: Existing browser client uses a legacy endpoint
- **WHEN** the v2 API is enabled and the current SPA requests an existing `/api` route
- **THEN** the legacy route retains its existing response shape

#### Scenario: Legacy retirement is considered
- **WHEN** maintainers later propose removing legacy routes
- **THEN** removal requires a separate documented change with migration evidence
