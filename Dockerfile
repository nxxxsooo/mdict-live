# Stage 1: Build React SPA
FROM node:22-alpine AS frontend
WORKDIR /app/website
COPY website/package.json website/package-lock.json ./
RUN npm ci
COPY website/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-alpine

WORKDIR /app

# Copy Flask source
COPY flask-mdict /app

# Remove all plugin files except __init__.py
RUN rm -f flask_mdict/plugins/[!__]*.py

# Remove 'translators' from requirements.txt to prevent installation
RUN sed -i '/translators/d' requirements.txt
# Install build dependencies for python-lzo
RUN apk add --no-cache lzo-dev build-base
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy built SPA from stage 1
# app.py resolves SPA at ../website/dist relative to flask-mdict dir
COPY --from=frontend /app/website/dist /website/dist

# Create content directory (volume mount point)
RUN mkdir -p content

# Expose the default port
EXPOSE 5248

# Run the application
CMD ["python", "app.py", "--host", "0.0.0.0:5248"]
