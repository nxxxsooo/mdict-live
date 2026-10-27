# MdictLive CLI

Small Python 3.11+ client for an MdictLive private v2 service. It uses only the
standard library and never opens local MDX files.

```bash
python -m pip install ./cli
mdict-live --url http://127.0.0.1:5248 sources
mdict-live --url https://dict.example/private --agent lookup "right"
```

Tokens should normally come from `MDICT_LIVE_TOKEN` or a mode-`0600` token
file. Run `mdict-live --help` for profile and command options.
