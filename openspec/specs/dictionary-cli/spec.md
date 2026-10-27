# dictionary-cli Specification

## Purpose

Defines a small standalone client for reliable local or remote dictionary access from terminals, scripts, Raycast commands, and other command-line workflows.

## Requirements

### Requirement: Installable standalone command
The project SHALL provide an installable `mdict-live` command that does not require the Flask source tree or a running local parser when connecting to a remote service.

#### Scenario: User checks the client version
- **WHEN** the user runs `mdict-live --version`
- **THEN** the command prints its client version and exits without contacting a server

#### Scenario: Client and server API versions differ
- **WHEN** the selected server does not expose a compatible v2 contract
- **THEN** the command exits with a compatibility error and does not fall back silently to an incompatible response

### Requirement: Profile-based connection configuration
The CLI SHALL support named profiles containing a base URL and non-secret defaults, with tokens supplied by environment variable, protected file reference, or explicit invocation.

#### Scenario: Default profile is used
- **WHEN** the user runs a command without connection flags
- **THEN** the CLI resolves the default profile and connects to its base URL

#### Scenario: Configuration sources overlap
- **WHEN** a flag, environment variable, and profile define the same setting
- **THEN** precedence is command flag, environment variable, selected profile, then built-in default

#### Scenario: Token is missing
- **WHEN** a protected remote endpoint is selected and no token can be resolved
- **THEN** the CLI exits with setup guidance without echoing other profile values that may be sensitive

#### Scenario: User requests minimal health without a token
- **WHEN** the user runs the health command without requesting authenticated details
- **THEN** the CLI calls unauthenticated liveness/readiness and does not require token resolution

### Requirement: Core dictionary commands
The CLI SHALL provide commands to inspect health, list sources, look up a query, resolve a citation, and request suggestions.

#### Scenario: User performs a lookup
- **WHEN** the user runs `mdict-live lookup <query>`
- **THEN** the CLI requests text results from enabled sources and prints entries with source labels and citations

#### Scenario: User filters lookup sources
- **WHEN** the user supplies one or more source selectors
- **THEN** the CLI resolves them unambiguously and sends only their `source_id` values

#### Scenario: Source selector is ambiguous
- **WHEN** a title fragment matches multiple sources
- **THEN** the CLI lists the matches and exits without choosing one

### Requirement: Human, JSON, and agent output modes
The CLI SHALL support a concise human default, stable JSON output, and a bounded agent mode containing plain text and citations but no raw HTML.

#### Scenario: Human output is requested on a terminal
- **WHEN** no output flag is provided
- **THEN** the CLI prints readable source sections, explicit partial/truncated markers, and citations

#### Scenario: JSON output is requested
- **WHEN** the user supplies `--json`
- **THEN** stdout contains one valid JSON document matching the v2 response contract and no progress decoration

#### Scenario: Agent output is requested
- **WHEN** the user supplies `--agent`
- **THEN** stdout contains bounded plain-text evidence with stable citations and excludes executable markup

### Requirement: Script-safe streams and exit codes
The CLI SHALL reserve stdout for requested data, send diagnostics to stderr, and use documented non-zero exit codes for configuration, authentication, transport, compatibility, validation, and server failures.

#### Scenario: Remote lookup succeeds with no match
- **WHEN** the server completes lookup and returns zero entries
- **THEN** the CLI emits a valid empty result and uses the documented no-match exit code

#### Scenario: Server returns a partial result
- **WHEN** at least one source completes and another fails, whether or not an entry matched
- **THEN** the CLI prints the partial result, marks it incomplete, and uses exit code 7

#### Scenario: Transport fails
- **WHEN** the server cannot be reached within the configured timeout outside JSON mode
- **THEN** stdout remains empty, stderr identifies the selected profile and failure category, and the CLI exits non-zero

#### Scenario: JSON mode encounters a handled error
- **WHEN** JSON mode encounters a local, transport, authentication, compatibility, validation, or server error
- **THEN** stdout contains one client error envelope, diagnostics remain on stderr, and the documented non-zero exit code identifies the category

#### Scenario: Complete result is truncated by a declared bound
- **WHEN** all selected sources complete but the server reports bounded output
- **THEN** the CLI marks truncation and exits 0 because truncation is part of the successful contract rather than a source failure

### Requirement: Explicit history recording
The CLI SHALL leave server search history unchanged by default and SHALL offer an explicit flag to record a successful lookup.

#### Scenario: Ordinary scripted lookup runs
- **WHEN** the user runs lookup without the history flag
- **THEN** the request does not ask the server to record history

#### Scenario: User opts into history
- **WHEN** the user supplies the history flag and at least one entry matches
- **THEN** the request asks the service to record that normalized query once

### Requirement: Secret-safe diagnostics
The CLI SHALL redact bearer tokens and credential-bearing URLs from normal output, verbose diagnostics, and error messages.

#### Scenario: Verbose request logging is enabled
- **WHEN** a user enables verbose diagnostics
- **THEN** method, redacted URL, timing, status, and request identifier may be shown while authorization values remain hidden
