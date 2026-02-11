# MdictLive

> A modern web reader for MDict dictionaries with React 19 SPA, dark mode, and faithful dictionary rendering.

> **📦 Formerly `flask-mdict`.** Both `tardivo/mdict-live` and `tardivo/flask-mdict` receive identical updates.

[GitHub Repository](https://github.com/nxxxsooo/mdict-live) | [Live Demo](https://dict.mjshao.fun)

## Features

- **React 19 SPA**: Fast, responsive, and modern interface.
- **Dark Mode**: Built-in dark theme support (`Ctrl+Shift+D`).
- **Sidebar**: Manage dictionaries and navigate easily.
- **Wordbook**: Save words to your favorites.
- **Word Frequency**: COCA/BNC ranking integration.
- **LZO Support**: Native support for LZO-compressed `.mdx` files.
- **Multi-Arch**: Supports `linux/amd64` and `linux/arm64`.

## Quick Start

**Bash**
```bash
docker run -d \
  --name mdict-live \
  -p 5248:5248 \
  -v $(pwd)/library:/app/content \
  tardivo/mdict-live:latest
```

**PowerShell**
```powershell
docker run -d `
  --name mdict-live `
  -p 5248:5248 `
  -v ${PWD}/library:/app/content `
  tardivo/mdict-live:latest
```

## Docker Compose

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

## Volumes

- `/app/content`: Directory containing your `.mdx` and `.mdd` files.
- `/config`: Directory for persistent configuration and database.

## Unraid

Use the XML template `mdict-live.xml` available in the [GitHub repository](https://github.com/nxxxsooo/mdict-live/blob/main/mdict-live.xml).
