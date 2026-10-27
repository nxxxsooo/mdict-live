# MdictLive tools for Pi

This Pi package registers four read-only tools:

- `mdict_sources`
- `mdict_lookup`
- `mdict_resolve`
- `mdict_suggest`

It also includes the `mdict-live-language-research` skill. The extension talks
only to the MdictLive v2 HTTP service and does not include a model provider.
Pi keeps ownership of OpenAI-compatible or Anthropic-compatible model routing.

Configure transport outside model-visible tool results:

```bash
export MDICT_LIVE_URL=http://127.0.0.1:5248
export MDICT_LIVE_TOKEN_FILE=$HOME/.config/mdict-live/token
chmod 600 "$MDICT_LIVE_TOKEN_FILE"
```

Install from the repository root:

```bash
pi install ./pi-package -l --approve
```

For a one-off smoke test without changing settings:

```bash
pi --no-extensions --no-skills \
  --extension ./pi-package/extensions/mdict-live.ts \
  --skill ./pi-package/skills/mdict-live-language-research \
  --tools mdict_sources,mdict_lookup,mdict_resolve,mdict_suggest
```
