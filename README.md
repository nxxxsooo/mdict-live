# Docker Flask Mdict Build

This repository contains a GitHub Actions workflow to automatically build and push the Docker image for [flask-mdict](https://github.com/liuyug/flask-mdict).

## Workflow

The workflow is defined in `.github/workflows/build.yml`.

**Triggers:**
- **Schedule:** Runs daily at 2:00 AM UTC.
- **Manual:** Can be triggered manually via the "Run workflow" button in the Actions tab.

**Steps:**
1. Check out the upstream repository (`liuyug/flask-mdict`).
2. Log in to Docker Hub using GitHub Secrets.
3. Build the Docker image from `upstream/Dockerfile`.
4. Push the image to `tardivo/flask-mdict:latest`.
5. Supports multi-architecture builds (`linux/amd64`, `linux/arm64`).


## Improvements & Changes in this Fork

This version includes several critical fixes and enhancements not present in the original:

1.  **Native LZO Compression**: Added full support for LZO-compressed MDX/MDD files by compiling `python-lzo` and installing system dependencies in the image. Resolves errors with "unknown compression method" for many older or Chinese dictionaries.
2.  **Reverse Proxy Support**: Added `ProxyFix` middleware to correctly handle `X-Forwarded-Proto` headers. Sites behind Nginx/Traefik will now load CSS/assets correctly via HTTPS.
3.  **Modernized Build**:
    -   Reduced image size by removing broken/unused translator plugins.
    -   Bind address set to `0.0.0.0` by default for Docker compatibility.
    -   Fixed `AttributeError: 'bytes' object has no attribute 'decode'` in MDX decoding logic.
4.  **Dictionary Tools**: Includes `tools/organize_dicts.py` to help bulk-rename and organize your dictionary library.

## Configuration

To use this workflow, ensuring the following **Secrets** are set in your repository (or Environment):

- `DOCKERHUB_USERNAME`: Your Docker Hub username.
- `DOCKERHUB_TOKEN`: Your Docker Hub Access Token.

> **Note:** If you are using GitHub Environments to protect these secrets, ensure the `environment` key is set correctly in `build.yml`.

## Deployment Options

### Option 1: Deploy from Docker Hub (Recommended)
Best for most users. Uses the pre-built, lean image from Docker Hub.

**Using Docker Compose:**
1.  Create `docker-compose.yml`:
    ```yaml
    version: '3.8'
    services:
      flask-mdict:
        image: tardivo/flask-mdict:latest
        restart: always
        ports:
          - "5248:5248"
        volumes:
          - ./library:/app/content
          - ./config:/config
    ```
2.  Run: `docker-compose up -d`

**Using Docker CLI:**

**PowerShell (Windows):**
```powershell
docker run -d `
  -v ${PWD}/library:/app/content `
  -p 5248:5248 `
  tardivo/flask-mdict:latest
```

**Command Prompt (Windows CMD):**
```cmd
docker run -d ^
  -v %cd%\library:/app/content ^
  -p 5248:5248 ^
  tardivo/flask-mdict:latest
```

**Bash (Mac/Linux):**
```bash
docker run -d \
  -v $(pwd)/library:/app/content \
  -p 5248:5248 \
  tardivo/flask-mdict:latest
```

### Option 2: Build from Source (Self-Build)
Best if you want to modify source code or bake dictionaries into the image.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/nxxxsooo/docker-flask-mdict.git
    cd docker-flask-mdict
    ```
2.  **Configure:** Uncomment `build: .` in `docker-compose.yml`.
3.  **Build & Run:**
    ```bash
    docker-compose up -d --build
    ```
2.  **Build and Run**:
    ```bash
    docker-compose up -d --build
    ```


