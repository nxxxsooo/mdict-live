# 📖 MdictLive

> A modern web reader for MDict dictionaries — React 19 SPA with dark mode, wordbook, and faithful dictionary rendering.

![MdictLive Screenshot](screenshots/screenshot-light.png)

MdictLive is a complete overhaul of the classic `flask-mdict` project, rebuilding the frontend as a modern Single Page Application (SPA) while preserving the robust Python backend for MDict file parsing.

It solves the biggest problem with existing web MDict viewers: **faithful rendering**. Instead of trying to sanitize or restyle the dictionary content (which breaks complex layouts), MdictLive treats each entry as a sovereign document, rendering it exactly as the dictionary author intended, while wrapping it in a modern, responsive interface.

## Features

- **Modern Tech Stack**: Built with React 19, Vite 7, and Tailwind v4.
- **Dark Mode**: Toggle with `Ctrl+Shift+D` or via settings.
- **Sidebar Navigation**: Manage multiple dictionaries, toggle visibility, and quick-jump.
- **Wordbook**: Star/favorite words for later review.
- **Instant Search**: Auto-suggestions and local search history.
- **Word Frequency**: Integrated COCA/BNC frequency data for English words.
- **Faithful Rendering**: Uses sandboxed iframes to preserve original dictionary CSS/JS.
- **LZO Compression**: Native support for older/Chinese dictionaries using LZO.
- **Reverse Proxy Ready**: Handles `X-Forwarded-Proto` correctly (HTTPS friendly).
- **Multi-Arch**: Docker images for `amd64` and `arm64` (Apple Silicon).

## Quick Start

### Docker Run

**Bash (Mac/Linux)**
```bash
docker run -d \
  --name mdict-live \
  -p 5248:5248 \
  -v $(pwd)/library:/app/content \
  tardivo/mdict-live:latest
```

**PowerShell (Windows)**
```powershell
docker run -d `
  --name mdict-live `
  -p 5248:5248 `
  -v ${PWD}/library:/app/content `
  tardivo/mdict-live:latest
```

### Docker Compose

```yaml
version: '3.8'
services:
  mdict-live:
    image: tardivo/mdict-live:latest
    container_name: mdict-live
    restart: unless-stopped
    ports:
      - "5248:5248"
    volumes:
      - ./library:/app/content
      - ./config:/config
```

## Configuration

| Path | Description |
|------|-------------|
| `/app/content` | **Required**. Place your `.mdx` and `.mdd` files here. Subdirectories are supported. |
| `/config` | Optional. Stores `flask_mdict.json` config and `flask_mdict.db` (history/favorites). |

## Tech Stack

- **Frontend**: React 19, Vite 7, Tailwind CSS v4, Zustand (State), React Query (Data), Framer Motion (Animations), Lucide React (Icons).
- **Backend**: Python 3.11, Flask, `mdict-utils` (modified for LZO).
- **Container**: Alpine Linux-based multi-stage build (Node.js build -> Python runtime).

## Building from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/nxxxsooo/mdict-live.git
   cd mdict-live
   ```

2. Build and run with Docker Compose:
   ```bash
   docker-compose up -d --build
   ```

The app will be available at `http://localhost:5248`.

## Credits

Forked from [liuyug/flask-mdict](https://github.com/liuyug/flask-mdict).
Major frontend rewrite and rebranding by [Mingjian Shao](https://mjshao.fun).

## Links

- [Live Demo](https://dict.mjshao.fun)
- [GitHub Repository](https://github.com/nxxxsooo/mdict-live)
- [Docker Hub](https://hub.docker.com/r/tardivo/mdict-live)
