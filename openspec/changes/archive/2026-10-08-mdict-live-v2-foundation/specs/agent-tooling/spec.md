## Purpose

Defines runtime-neutral, read-only dictionary tools and a Pi reference bundle so agents can investigate language with bounded, source-cited evidence without coupling MdictLive to a model provider.

## ADDED Requirements

### Requirement: Runtime-neutral tool schemas
The project SHALL publish versioned JSON-compatible schemas for source listing, dictionary lookup, citation resolution, and suggestions that map directly to the v2 API.

#### Scenario: Non-Pi client implements the tools
- **WHEN** an MCP server, Raycast extension, or another agent runtime consumes the published schemas
- **THEN** it can call the dictionary service without importing Pi-specific code

#### Scenario: Tool contract changes incompatibly
- **WHEN** a future change removes or redefines a required field
- **THEN** the tool schema version changes and existing clients receive an explicit incompatibility signal

### Requirement: Read-only bounded evidence tools
Agent-facing tools SHALL be read-only by default and SHALL return plain-text evidence, source metadata, citations, and explicit truncation information without raw executable HTML.

#### Scenario: Agent looks up a word across sources
- **WHEN** the lookup tool is called with a query and no source selection
- **THEN** it returns bounded evidence from enabled sources in deterministic order

#### Scenario: Evidence exceeds the tool budget
- **WHEN** the service has more matching text than the configured tool bound
- **THEN** the tool returns the bounded subset with a truncation marker and enough identity to request a narrower follow-up

#### Scenario: Agent attempts a state change through a read tool
- **WHEN** tool input includes unsupported mutation intent
- **THEN** validation rejects the input before any service state changes

### Requirement: Evidence and inference separation
The reference agent workflow SHALL distinguish dictionary evidence from its own synthesis and SHALL attach stable citations to claims derived from dictionary content.

#### Scenario: Multiple sources disagree
- **WHEN** retrieved dictionaries present materially different senses or usage guidance
- **THEN** the agent reports the disagreement with citations rather than collapsing it into an uncited single answer

#### Scenario: Evidence is insufficient
- **WHEN** available dictionary results do not support a requested conclusion
- **THEN** the agent states that evidence is insufficient and may request a narrower or related lookup

#### Scenario: Agent provides a synthesized explanation
- **WHEN** the agent combines evidence into an explanation
- **THEN** factual lexical claims include citations and generated examples are labeled as generated

### Requirement: Optional Pi reference package
The project SHALL provide an installable Pi package containing the dictionary tool extension and language-research skill, while leaving ordinary MdictLive deployment independent of Pi.

#### Scenario: User installs the Pi package
- **WHEN** the package is installed through Pi's supported package mechanism
- **THEN** Pi discovers the versioned tools and skill without modifying the MdictLive server

#### Scenario: Pi package is not installed
- **WHEN** a user runs the server, web reader, or CLI without Pi
- **THEN** deterministic dictionary features remain fully available

### Requirement: Host-owned model configuration
The agent bundle SHALL use the host runtime's configured provider and model and SHALL contain no embedded provider credential, mandatory model, or direct sub2api dependency.

#### Scenario: Pi is configured for sub2api
- **WHEN** the host selects an OpenAI-compatible or Anthropic-compatible sub2api model such as GPT-5.6 Luna or Sonnet 5
- **THEN** the bundle uses that active model through Pi without translating credentials through MdictLive

#### Scenario: Host selects another compatible provider
- **WHEN** Pi uses a different supported provider
- **THEN** the dictionary tools and workflow continue to operate without a server change

### Requirement: Client-owned service credentials
Agent adapters SHALL resolve the MdictLive URL and token from client configuration and SHALL not expose them to the language model or tool result.

#### Scenario: Agent calls a remote private service
- **WHEN** the adapter authenticates to a self-hosted MdictLive URL
- **THEN** the token is used only in the transport layer and is absent from model-visible input and output

#### Scenario: Authentication fails
- **WHEN** the service rejects the configured token
- **THEN** the tool returns a bounded authentication error with setup guidance and no credential echo

### Requirement: Partial failure transparency
Agent tools SHALL preserve v2 partial-result and request-identifier information so an agent can reason about missing evidence.

#### Scenario: One dictionary source times out
- **WHEN** a lookup tool receives successful entries and a per-source failure
- **THEN** the tool returns both the evidence and a structured warning naming the unavailable `source_id`

