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

## Configuration

To use this workflow, ensuring the following **Secrets** are set in your repository (or Environment):

- `DOCKERHUB_USERNAME`: Your Docker Hub username.
- `DOCKERHUB_TOKEN`: Your Docker Hub Access Token.

> **Note:** If you are using GitHub Environments to protect these secrets, ensure the `environment` key is set correctly in `build.yml`.

## Usage with Docker Compose

To run the application with persistent configuration and dictionary files, use the included `docker-compose.yml`.

1.  **Create Directories:**
    ```bash
    mkdir library config
    ```
2.  **Add Dictionaries:** Put your `.mdx` and `.mdd` files into the `library` folder.
3.  **Add Config:** Create/copy your `flask_mdict.json` into the `config` folder.
    *   *Tip: You can extract the default config from the image first if needed.*
4.  **Run:**
    ```bash
    docker-compose up -d
    ```

The application will be available at `http://localhost:5248`.
- Dictionaries & Database (`flask_mdict.db`) are stored in `./library`.
- Configuration (`flask_mdict.json`) is stored in `./config`.

## Building Locally with Docker Compose

If you want to build the image yourself (e.g., to include modifications):

1.  **Edit `docker-compose.yml`**:
    Uncomment the `build: .` line:
    ```yaml
    services:
      flask-mdict:
        build: .
        # image: ... (optional: comment out image to force checking local build)
    ```
2.  **Build and Run**:
    ```bash
    docker-compose up -d --build
    ```


