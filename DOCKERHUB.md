# Flask-MDict Docker Image

A Dockerized version of [flask-mdict](https://github.com/liuyug/flask-mdict), a web-based MDict dictionary viewer.

## Features

*   **Web Interface**: Access your dictionaries from any browser.
*   **Format Support**: Fully supports `.mdx` and `.mdd` files.
*   **Persistence**: Keep your dictionaries and configuration safe across restarts.
*   **Multi-Arch**: Supports `amd64` and `arm64`.

## Quick Start

```bash
docker run -d \
  --name flask-mdict \
  -p 5248:5248 \
  -v ./library:/app/content \
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

## Recent Changes
-   **No Plugins**: Translator plugins are removed for a leaner image.
-   **Security**: Default bind address is `0.0.0.0` (Docker friendly).
-   **Fixes**: Includes fixes for MDX decoding errors.

## Unraid

An XML template is available in the GitHub repository (`flask-mdict.xml`) for easy installation on Unraid.

## License

Based on `flask-mdict` (MIT License).
