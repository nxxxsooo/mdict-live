FROM python:3.11-alpine

WORKDIR /app

# Copy the source code from the 'flask-mdict-source' directory
COPY flask-mdict /app

# Remove all plugin files except __init__.py
RUN rm -f flask_mdict/plugins/[!__]*.py

# Remove 'translators' from requirements.txt to prevent installation
RUN sed -i '/translators/d' requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create content directory (volume mount point)
RUN mkdir -p content
# COPY content/source /app/content  <-- Removed: Using volume mounts only


# Expose the default port
EXPOSE 5248

# Run the application
CMD ["python", "app.py", "--host", "0.0.0.0:5248"]
