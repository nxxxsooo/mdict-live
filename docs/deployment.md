# Private deployment

MdictLive v2 is a private dictionary service. The v2 API always requires a
bearer token, but compatibility routes under `/api` and `/mdict` remain
unauthenticated during the migration. Keep the whole origin inside localhost,
a LAN/VPN boundary, or an authenticated reverse proxy. Public Internet exposure
of the compatibility routes is unsupported.

## Prepare the token

Create a random value of at least 32 bytes and store it in a protected file.
Do not put the token in Compose YAML, an Unraid XML template, a URL, or browser
local storage. The image runs as UID/GID `1000:1000`: direct Docker Run and
Unraid bind mounts must make the file readable by that identity, preferably
owner `1000:1000` and mode `0400`. Compose mounts its declared Docker secret
through `/run/secrets`.

```bash
mkdir -p secrets
openssl rand -hex 32 > secrets/mdict-live-token
chmod 600 secrets/mdict-live-token
```

For a direct bind mount on Linux or Unraid, set the final ownership and mode:

```bash
chown 1000:1000 secrets/mdict-live-token
chmod 0400 secrets/mdict-live-token
```

The `/data`, `/data/index`, and `/config` host directories must likewise be
writable by UID/GID `1000:1000`. Do not solve a permission error by making the
read-only corpus writable.

The browser accepts the token for the current tab through Settings and keeps it
in session storage. The CLI should use `--token-file` or a profile `token_file`;
the Pi package can use `MDICT_LIVE_TOKEN_FILE`.

## Local Compose

```bash
docker compose up -d --build
curl -fsS http://127.0.0.1:5248/health/ready
open http://127.0.0.1:5248/app/
```

The canonical mounts are:

| Container path | Access | Purpose |
|---|---|---|
| `/library` | read-only | MDX/MDD corpus and optional legacy database for one-time adoption |
| `/data` | read/write | application database and migration state |
| `/data/index` | read/write | generated, disposable indexes |
| `/config` | read/write | non-secret configuration |
| `/run/secrets/mdict_live_token` | read-only | bearer secret file |

Enable the optional in-memory Valkey service with:

```bash
COMPOSE_PROFILES=cache REDIS_URL=redis://valkey:6379/0 docker compose up -d
```

## Nginx Proxy Manager

The simplest and preferred NPM layout uses a dedicated private hostname and
forwards the complete origin to `mdict-live:5248` on the same Docker network.
Enable WebSocket support only if another application on the host needs it;
MdictLive does not require it. Set:

```text
MDICT_TRUSTED_PROXY_HOPS=1
MDICT_TRUSTED_PROXY_CIDRS=172.16.0.0/12
```

Use the actual narrow Docker subnet instead of `172.16.0.0/12` when practical.
Do not trust forwarded headers from arbitrary LAN clients.

For a public prefix such as `/dictionary`, the proxy must strip the prefix on
the upstream request and send the original prefix explicitly:

```nginx
location /dictionary/ {
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /dictionary;
    rewrite ^/dictionary/(.*)$ /$1 break;
    proxy_pass http://mdict-live:5248;
}
```

The workspace uses relative assets and derives API/resource paths from the
`/app/` mount, so `/dictionary/app/`, `/dictionary/api/`,
`/dictionary/assets/`, and `/dictionary/mdict/` remain under the same prefix.
The CLI profile URL is the prefix itself, for example:

```toml
default_profile = "home"

[profiles.home]
url = "https://private.example/dictionary"
token_file = "token"
```

## Tailscale and ZeroTier

For direct private-network access, publish port `5248` on the host and connect
to the host's Tailscale or ZeroTier address. Keep v2 authentication enabled even
inside the VPN. If other LAN users can reach the same port, remember that the
legacy endpoints are still trusted-network-only.

Examples:

```bash
mdict-live --url http://100.x.y.z:5248 health
mdict-live --url http://10.z.y.x:5248 lookup right
```

Do not set proxy trust merely because the request arrived through a VPN. Set
`MDICT_TRUSTED_PROXY_HOPS=0` for direct Tailscale/ZeroTier access unless an
actual reverse proxy is the immediate peer.

## Token rotation

Replace the secret file atomically and recreate or restart the container.
Rotation invalidates previously issued citation resolver tokens and short-lived
asset capabilities because their HMAC keys derive from the secret by default.
Browser, CLI, and Pi clients must then load the new token. Never log the old or
new value while validating the rotation.
