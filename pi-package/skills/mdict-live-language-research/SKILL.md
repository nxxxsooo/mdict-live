---
name: mdict-live-language-research
description: Research words, phrases, usage, contrasts, etymology, and translation choices with private MdictLive sources. Use when lexical claims should be grounded in source-cited dictionary evidence.
compatibility: Requires the @mdict-live/pi-tools extension plus MDICT_LIVE_URL and MDICT_LIVE_TOKEN or MDICT_LIVE_TOKEN_FILE.
allowed-tools: mdict_sources mdict_lookup mdict_resolve mdict_suggest
---

# MdictLive Language Research

Use the MdictLive tools as a deterministic evidence layer. The active Pi model may explain and compare the evidence, but it must not blur retrieved dictionary text with its own synthesis.

## Workflow

1. Call `mdict_lookup` with the exact user expression. Preserve punctuation and internal spaces unless the user asks for variants.
2. If no exact entry matches, call `mdict_suggest`. Set `fuzzy: true` only when ordinary prefix suggestions are inadequate, and tell the user that a fallback spelling was used.
3. For source comparison, call `mdict_sources` when source identity or availability is unclear, then pass stable `source_ids` to focused lookups.
4. Compare meanings, grammar, register, collocations, examples, and regional labels only when the returned text supports those dimensions.
5. Cite lexical claims with the returned `mdict://` URI. Prefer the most specific text-block citation over a whole-entry citation.
6. Use `mdict_resolve` when a protected citation token needs to be checked against the current source revision.

## Evidence Rules

- Label directly retrieved text or close paraphrase as dictionary evidence and name its source ID or title.
- Label cross-source conclusions as inference. Cite every supporting source and say when sources disagree.
- Label every newly written example sentence as `Generated example`; never imply that it came from a dictionary.
- Treat `partial: true`, failed sources, omitted source IDs, and truncation causes as material limitations. State them before drawing a broad conclusion.
- Do not infer that no word exists when sources failed or were omitted.
- Do not quote or reconstruct raw source HTML. Tool results intentionally contain bounded text evidence only.
- Never expose the service URL, bearer token, token-file path, or transport configuration. They are not evidence.

## Insufficient Evidence

If the returned evidence does not support the requested nuance, say exactly what is missing. Offer a narrower lookup, a source-specific comparison, or an explicitly labeled general-language inference. Do not manufacture a dictionary consensus.
