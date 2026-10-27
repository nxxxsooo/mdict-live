# MdictLive

Private, self-hosted MDict reading workspace and evidence service with a React
client, bearer-protected v2 API, standalone CLI, and read-only Pi tools.

> v2 must stay on localhost, a trusted LAN/VPN, or behind a private authenticated
> reverse proxy. Legacy compatibility routes remain unauthenticated during the
> transition, so direct public-Internet exposure is unsupported.

## Container contract

| Path | Access | Purpose |
|---|---|---|
| `/library` | read-only | `.mdx`/`.mdd` corpus |
| `/data` | read/write | database and migration state |
| `/data/index` | read/write | generated indexes |
| `/config` | read/write | non-secret configuration |
| `/run/secrets/mdict_live_token` | read-only | token file, minimum 32 random bytes |

The image runs as a non-root user under Gunicorn and includes a readiness health
check at `/health/ready`. On Linux, make the writable directories and directly
bind-mounted token readable by UID/GID `1000:1000`; mode `0400` with that owner
is recommended for the token.

```bash
docker run -d \
  --name mdict-live \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -p 127.0.0.1:5248:5248 \
  -v "$PWD/library:/library:ro" \
  -v "$PWD/data:/data" \
  -v "$PWD/index:/data/index" \
  -v "$PWD/config:/config" \
  -v "$PWD/secrets/mdict-live-token:/run/secrets/mdict_live_token:ro" \
  tardivo/mdict-live:latest
```

Open `http://127.0.0.1:5248/app/`. Optional Valkey/Redis caching is enabled with
`REDIS_URL=redis://host:6379/0`.

For Compose, Unraid, Nginx Proxy Manager, Tailscale, ZeroTier, prefix hosting,
token rotation, and v1 volume migration, use the repository documentation:

- [Deployment guide](https://github.com/nxxxsooo/mdict-live/blob/main/docs/deployment.md)
- [Migration guide](https://github.com/nxxxsooo/mdict-live/blob/main/docs/migration.md)
- [Unraid template](https://github.com/nxxxsooo/mdict-live/blob/main/mdict-live.xml)

Images target `linux/amd64` and `linux/arm64`.
