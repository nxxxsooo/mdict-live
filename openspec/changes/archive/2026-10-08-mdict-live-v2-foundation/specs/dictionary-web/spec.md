## Purpose

Defines the private browser workspace that presents deterministic metadata and agent assistance around source-faithful MDict entries without forcing arbitrary lexicons into one normalized visual schema.

## ADDED Requirements

### Requirement: Reference workspace shell
The browser client SHALL provide one coherent workspace for search, source navigation, saved words, history, citations, and contextual explanation while keeping dictionary entry documents visually distinct from application controls.

#### Scenario: Lookup returns multiple source entries
- **WHEN** a lookup matches more than one enabled dictionary
- **THEN** the workspace presents one continuous result page in configured source order with persistent source identity and navigation for every entry

#### Scenario: User navigates to a source
- **WHEN** the user selects a source from the source ledger
- **THEN** the workspace moves to that source entry without issuing a duplicate lookup or losing the current query

### Requirement: Native source document is the default representation
The browser client SHALL render each dictionary's safe HTML and source-owned CSS as a native source document by default and SHALL NOT translate arbitrary dictionary markup into a universal definition component or cascade workspace CSS into the source document.

#### Scenario: CSS-heavy dictionary entry is rendered
- **WHEN** a source returns safe HTML with source-specific selectors, fonts, tables, labels, and layout rules
- **THEN** those rules remain scoped to that source document and the entry retains its source-specific presentation without changing the workspace shell

#### Scenario: Two sources use conflicting selectors
- **WHEN** two returned entries both define global selectors such as `body`, `a`, or `.entry`
- **THEN** neither source stylesheet affects the other source document or the surrounding application

#### Scenario: Source has minimal or no CSS
- **WHEN** a source returns safe HTML without a usable stylesheet
- **THEN** the client applies only a bounded neutral document baseline for readability without reconstructing the lexical structure

### Requirement: Opaque-origin rendering boundary
The browser client SHALL render native source documents in a sandboxed boundary that does not grant `allow-same-origin`, top-level navigation, form submission, popups, downloads, or authenticated application-origin access by default.

#### Scenario: Dictionary markup contains executable script
- **WHEN** dictionary-provided markup originally contains a script, inline event handler, or `javascript:` URL
- **THEN** the representation pipeline removes or makes it inert before rendering and it cannot execute in the source document

#### Scenario: Source document attempts application-origin access
- **WHEN** content in the source document attempts to read application storage, cookies, DOM, or authenticated API state
- **THEN** the opaque-origin boundary prevents that access

#### Scenario: Application bridge must execute
- **WHEN** the client injects its own resize and interaction bridge after sanitization
- **THEN** the frame may grant only the script capability required by that application-owned bridge while continuing to omit `allow-same-origin`

### Requirement: Typed native-document bridge
The browser client SHALL limit communication with source documents to application-owned typed messages for content size, entry navigation, sound playback, and explicitly supported media actions.

#### Scenario: Source content height changes
- **WHEN** fonts, images, expandable content, or responsive layout change a native document's height
- **THEN** the bridge reports a bounded height and the parent adjusts the frame without requiring nested page scrolling under normal entry sizes

#### Scenario: Internal entry link is activated
- **WHEN** the user activates a rewritten MDict entry link inside a source document
- **THEN** the bridge sends the normalized target word to the parent and the workspace performs an ordinary lookup

#### Scenario: Forged or unrelated message is received
- **WHEN** the parent receives a bridge-like message from an unexpected window, with an invalid frame capability, or with an unsupported action or payload
- **THEN** the client ignores it without changing state or accessing a resource

#### Scenario: Bridge initialization fails
- **WHEN** a native document cannot initialize or report through the bridge
- **THEN** the entry remains available through a bounded scroll or dedicated safe-source view rather than disappearing

### Requirement: Source-scoped resource fidelity
The browser client SHALL allow safe dictionary images, fonts, stylesheets, sounds, and nested CSS resources to load through source- and revision-scoped capability URLs without exposing the API bearer token or host filesystem paths.

#### Scenario: Native stylesheet references a font and image
- **WHEN** the source document loads rewritten CSS containing nested font and image URLs
- **THEN** the resources resolve through valid source-scoped capabilities and retain the entry's visual structure

#### Scenario: Resource capability has expired
- **WHEN** a visible entry attempts to load an expired resource capability
- **THEN** the client may refresh the entry representation once and otherwise reports a source-specific degraded-media state without failing other entries

### Requirement: Workspace theme does not rewrite native source colors
The browser client SHALL apply light or dark themes to application-owned surfaces without globally inverting, recoloring, or injecting theme CSS into native source documents.

#### Scenario: Dark workspace displays a light-only dictionary
- **WHEN** the workspace is dark and the source document declares a light color scheme
- **THEN** the source remains a light document inside a clearly bounded native surface

#### Scenario: Dictionary provides an explicit compatible theme
- **WHEN** a source adapter declares and tests a source-owned dark theme
- **THEN** the client may select it without applying generic color inversion or modifying unrelated source rules

### Requirement: Derived guidance remains separate from dictionary evidence
Quick senses, structured metadata, contextual agent explanations, and generated examples SHALL appear in application-owned surfaces and SHALL remain distinguishable from native dictionary entries and their citations.

#### Scenario: Structured quick sense is available
- **WHEN** the metadata capability returns a definition or translation from a named dataset
- **THEN** the workspace may show it above native entries with its dataset identity and without presenting it as an extracted source entry

#### Scenario: Preferred source exposes a citable first sense
- **WHEN** a configured preferred source returns an ordered definitional text block with a stable citation
- **THEN** the workspace may show that exact block as Quick Sense with its source, grammatical role, and citation while identifying it as the first source sense rather than a summary of every homograph

#### Scenario: Quick sense requires synthesis across senses
- **WHEN** no deterministic metadata or citable source block adequately represents the requested overview
- **THEN** any synthesized text is labeled as an AI overview, includes its supporting citations, and is never presented as dictionary-authored text

#### Scenario: Agent explains a word in context
- **WHEN** the user requests a contextual explanation
- **THEN** the explanation appears outside native source documents, identifies the source citations it used, and labels generated examples as generated

#### Scenario: Agent capability is unavailable
- **WHEN** no compatible model client or agent bundle is configured
- **THEN** deterministic search, native entry rendering, citations, history, and saved words remain usable

### Requirement: Safe dedicated source view
The browser client SHALL provide a dedicated source view for entries that need more space or fidelity inspection, and that view SHALL use the same sanitized HTML, resource capabilities, and opaque-origin trust boundary rather than an unsanitized raw document.

#### Scenario: Entry exceeds embedded presentation bounds
- **WHEN** an entry is taller than the configured embedded limit or contains a complex table that is difficult to inspect inline
- **THEN** the workspace offers an explicit full-source view while keeping the primary multi-source page responsive

#### Scenario: User opens the dedicated source view
- **WHEN** the dedicated view is opened
- **THEN** source identity, revision, citation action, and a return path to the multi-source lookup remain available

### Requirement: Responsive source navigation and reading
The browser client SHALL retain search, source navigation, native-entry readability, citation actions, and contextual explanation at desktop and narrow phone widths without horizontal page overflow.

#### Scenario: Workspace is viewed at a desktop width
- **WHEN** sufficient width is available
- **THEN** the source ledger remains visible beside a bounded continuous reading sheet

#### Scenario: Workspace is viewed at a phone width
- **WHEN** the viewport cannot fit the ledger and reading sheet together
- **THEN** source navigation becomes an off-canvas control, native frames reflow within the reading width, and closing a panel returns keyboard focus to its trigger

### Requirement: Complete lookup state feedback
The browser client SHALL provide distinct accessible states for initial search, loading, complete results, no match, partial source failure, total lookup failure, and unavailable native rendering.

#### Scenario: Lookup is in progress
- **WHEN** a lookup has not completed
- **THEN** the result region reports a busy state and shows a stable loading layout without erasing the active query

#### Scenario: Some sources fail
- **WHEN** the API returns successful entries with `partial: true`
- **THEN** the workspace renders completed source entries and identifies each failed or omitted source without presenting the lookup as wholly failed

#### Scenario: No source contains the query
- **WHEN** all selected sources complete with no entry
- **THEN** the workspace shows a no-match state distinct from connection or source failure

### Requirement: Accessible native-content controls
Application-owned controls around native documents SHALL be keyboard reachable, visibly focused, and programmatically labeled, and hidden drawers or frames SHALL NOT retain focusable descendants.

#### Scenario: User navigates by keyboard
- **WHEN** the user tabs through search, source navigation, citations, saved words, and context controls
- **THEN** focus order follows the visible workspace and every action has a visible focus indicator

#### Scenario: User closes an off-canvas panel
- **WHEN** a source ledger or context panel closes while focus is inside it
- **THEN** focus returns to the control that opened it and the hidden panel becomes inert

#### Scenario: User prefers reduced motion
- **WHEN** the operating system requests reduced motion
- **THEN** smooth scrolling, drawer animation, and frame-height animation are reduced or disabled without losing functionality
