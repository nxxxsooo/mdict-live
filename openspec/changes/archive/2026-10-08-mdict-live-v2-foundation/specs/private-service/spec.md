## Purpose

Defines the trust, storage, proxy, and operational boundaries required to run MdictLive safely as a private local or self-hosted single-user service.

## ADDED Requirements

### Requirement: Single-user API token authentication
Every `/api/v2` endpoint SHALL require a configured bearer token on loopback and non-loopback deployments and SHALL compare credentials without revealing token material. Minimal health routes and signed asset-capability routes SHALL remain outside `/api/v2` and use their own bounded authorization contracts.

#### Scenario: Valid client token is supplied
- **WHEN** a client sends `Authorization: Bearer <token>` with the configured token
- **THEN** the service processes the protected request

#### Scenario: Token is absent or invalid
- **WHEN** a protected endpoint receives no token or an invalid token
- **THEN** the service returns HTTP 401 with a generic JSON error and no indication of which token characters matched

#### Scenario: Service binds beyond loopback without a token
- **WHEN** v2 protected endpoints are enabled on a non-loopback bind and no token is configured
- **THEN** startup fails closed with configuration guidance

#### Scenario: Loopback service has no token
- **WHEN** v2 endpoints are enabled on a loopback-only bind and no token is configured
- **THEN** startup fails closed with the same configuration guidance

### Requirement: Minimal unauthenticated health surface
The service SHALL expose unauthenticated liveness and readiness checks containing no dictionary names, filesystem paths, cache URLs, tokens, or user activity.

#### Scenario: Process is alive
- **WHEN** an orchestrator requests liveness
- **THEN** the service returns HTTP 200 if the process can serve requests

#### Scenario: Dictionary initialization is incomplete
- **WHEN** an orchestrator requests readiness before required storage and source initialization complete
- **THEN** the service returns HTTP 503 with a minimal readiness state

### Requirement: Explicit cross-origin policy
The service SHALL reject browser origins that are not on an explicit allowlist and SHALL not reflect arbitrary request origins.

#### Scenario: Non-browser client omits Origin
- **WHEN** an authenticated CLI or agent client sends no `Origin` header
- **THEN** the service evaluates authentication normally without adding permissive CORS headers

#### Scenario: Allowed browser origin sends a preflight request
- **WHEN** the exact origin is configured and requests an allowed method and header
- **THEN** the service returns a matching, bounded preflight response

#### Scenario: Unknown browser origin calls the API
- **WHEN** an origin is not configured
- **THEN** the service omits access-control permission and rejects state-changing preflight requests

### Requirement: Bounded reverse-proxy trust
The service SHALL honor forwarded scheme, host, client address, and prefix headers only from an explicitly configured trusted proxy boundary.

#### Scenario: Request arrives from the trusted proxy
- **WHEN** a configured Nginx Proxy Manager address forwards a request
- **THEN** generated external URLs use the approved forwarded scheme, host, and prefix

#### Scenario: Direct client spoofs forwarded headers
- **WHEN** a request outside the configured proxy boundary supplies forwarded headers
- **THEN** the service ignores those headers for security and URL generation decisions

### Requirement: Separated storage roles
The deployment SHALL support a read-only dictionary library, a writable application-data directory, and a writable generated-index directory.

#### Scenario: Service starts with a read-only corpus
- **WHEN** `.mdx` and `.mdd` files are mounted read-only and writable data/index paths are configured
- **THEN** discovery and lookup work without attempting to create databases or description files inside the corpus

#### Scenario: Writable state persists across container replacement
- **WHEN** the container is recreated with the same data and index volumes
- **THEN** history, wordbooks, settings, source registry, and reusable indexes remain available

### Requirement: Non-destructive legacy data migration
The service SHALL detect the current single-content-directory layout and SHALL migrate or reuse its application database and generated indexes without deleting dictionary files or user records.

#### Scenario: Existing application database is present in the corpus mount
- **WHEN** the service starts with a legacy `flask_mdict.db` and an empty v2 data directory
- **THEN** it copies the database transactionally into the v2 data directory and records the migration result

#### Scenario: Migration cannot complete
- **WHEN** permissions, corruption, or a conflicting destination prevents migration
- **THEN** startup stops before writing partial state and reports a recoverable error

### Requirement: Safe dictionary content handling
Dictionary-provided markup SHALL be treated as untrusted content, and executable entry scripts SHALL be inert by default in v2 rendering.

#### Scenario: Entry contains JavaScript
- **WHEN** a client requests the default HTML representation
- **THEN** the returned renderable representation cannot execute the dictionary script in the authenticated application origin

#### Scenario: Entry references a packaged resource
- **WHEN** HTML references an image, font, stylesheet, or sound from the dictionary
- **THEN** the service exposes that resource through a short-lived signed source/revision/path capability URL without placing the bearer token in the URL

#### Scenario: Signed resource capability expires
- **WHEN** a dictionary resource URL is requested after its capability expiry or with an invalid signature
- **THEN** the service returns HTTP 401 without exposing whether the underlying resource exists

#### Scenario: Resource path attempts traversal
- **WHEN** a resource request contains encoded or decoded parent traversal
- **THEN** the service rejects it without reading a host file

### Requirement: Secret-safe configuration and logging
The service SHALL accept the API token from a secret-capable environment or file reference and SHALL never return or log the token.

#### Scenario: Authentication fails
- **WHEN** a request supplies an invalid token
- **THEN** logs include only the request identifier, route, and failure category

#### Scenario: Diagnostic status is requested
- **WHEN** an authenticated client requests detailed status
- **THEN** configured secret values and credential-bearing cache URLs are redacted

### Requirement: Scoped state-changing operations
State-changing v2 endpoints SHALL require authentication, use explicit HTTP methods, validate request content types, and report whether a target changed.

#### Scenario: Client changes source enablement
- **WHEN** an authenticated client sends a valid state-change request
- **THEN** the service persists the new state and returns the resulting representation

#### Scenario: Cross-site form submits to a state-changing route
- **WHEN** a request has an unsupported content type or disallowed browser origin
- **THEN** the service rejects it before changing state

### Requirement: Private deployment documentation
The distribution SHALL document supported local, Docker, Unraid, Nginx Proxy Manager, Tailscale, and ZeroTier deployment boundaries and SHALL state that direct public-Internet exposure is unsupported, even when v2 token authentication is enabled.

#### Scenario: User follows the self-hosted guide
- **WHEN** a user deploys the documented Compose or Unraid configuration
- **THEN** the corpus is read-only, data and index storage are persistent, a token is required, and the health check is usable

#### Scenario: Legacy routes remain during migration
- **WHEN** a deployment still serves legacy `/api` or browser routes
- **THEN** documentation requires the entire service to remain behind the private VPN/network boundary rather than exposing only v2 authentication to the public Internet
