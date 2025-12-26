# Use the latest Python 3.13 slim image (Debian-based)
# This is the best balance of size and compatibility for Flask
FROM python:3.13-slim

# Set environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files
# PYTHONUNBUFFERED: Ensures logs are streamed directly to the container logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies (Optional)
# If your Flask app needs cURL, git, or specific C-libs, uncomment the lines below:
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     gcc libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create a non-root user specifically for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Define the ENTRYPOINT and CMD
# Using ENTRYPOINT ["python"] makes this container act like a python executable
# You can just pass the script name when running it
ENTRYPOINT ["python"]

# Default argument to ENTRYPOINT
CMD ["app.py"]