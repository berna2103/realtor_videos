# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install FFmpeg and other required system libraries for MoviePy/OpenCV
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create output directories to prevent mount crashes
RUN mkdir -p output raw_photos

# Railway automatically provides a $PORT environment variable. 
# We run Uvicorn on that port.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]