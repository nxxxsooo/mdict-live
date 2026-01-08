# Flask-MDict Docker Image

A Dockerized version of [flask-mdict](https://github.com/liuyug/flask-mdict) with significant improvements for modern deployment.
- **GitHub Repository**: [nxxxsooo/docker-flask-mdict](https://github.com/nxxxsooo/docker-flask-mdict)
- **DockerHub**: [tardivo/flask-mdict](https://hub.docker.com/r/tardivo/flask-mdict)

## Features

*   **Web Interface**: Access your dictionaries from any browser.
*   **Format Support**: Fully supports `.mdx` and `.mdd` files.
*   **Persistence**: Keep your dictionaries and configuration safe across restarts.
*   **Multi-Arch**: Supports `amd64` and `arm64`.

## Quick Start

**Bash (Mac/Linux):**
```bash
docker run -d \
  --name flask-mdict \
  -p 5248:5248 \
  -v $(pwd)/library:/app/content \
  tardivo/flask-mdict:latest
```

**PowerShell (Windows):**
```powershell
docker run -d `
  --name flask-mdict `
  -p 5248:5248 `
  -v ${PWD}/library:/app/content `
  tardivo/flask-mdict:latest
```

**Command Prompt (Windows CMD):**
```cmd
docker run -d ^
  --name flask-mdict ^
  -p 5248:5248 ^
  -v %cd%\library:/app/content ^
  tardivo/flask-mdict:latest
```

## Configuration

### Volumes

| Container Path | Description | Suggested Host Path |
| :--- | :--- | :--- |
| `/app/content` | Stores dictionary files (`.mdx`, `.mdd`) and the database. | `./library` |
| `/config` | Stores the `flask_mdict.json` configuration file. | `./config` |

### Custom Configuration File

To use a custom `flask_mdict.json`, map a volume to `/config` and override the command:

```yaml
version: '3.8'
services:
  flask-mdict:
    image: tardivo/flask-mdict:latest
    ports:
      - "5248:5248"
    volumes:
      - ./library:/app/content
      - ./config:/config
    command: ["python", "app.py", "--config-file", "/config/flask_mdict.json"]
```

## Running Locally (Docker Compose)

To build the image locally with your own modifications:

1.  Clone the repository.
2.  Uncomment `build: .` in `docker-compose.yml`.
3.  Run `docker-compose up -d --build`.

## Improvements & Changes in this Fork

This version includes several critical fixes and enhancements not present in the original:

1.  **Reverse Proxy Support**: Added `ProxyFix` middleware to correctly handle `X-Forwarded-Proto` headers. Sites behind Nginx/Traefik will now load CSS/assets correctly via HTTPS.
2.  **LZO Compression Support**: Fixed issues with identifying and handling LZO-compressed MDX files.
3.  **Modernized Build**:
    -   Reduced image size by removing broken/unused translator plugins.
    -   Bind address set to `0.0.0.0` by default for Docker compatibility.
    -   Fixed `AttributeError: 'bytes' object has no attribute 'decode'` in MDX decoding logic.
4.  **Dictionary Tools**: Includes `tools/organize_dicts.py` to help bulk-rename and organize your dictionary library.

## Unraid

An XML template is available in the GitHub repository (`flask-mdict.xml`) for easy installation on Unraid.

## License

Based on `flask-mdict` (MIT License).
