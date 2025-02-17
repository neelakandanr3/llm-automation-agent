# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    nodejs \
    npm \
    tesseract-ocr \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only the necessary files first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install the standard-aifc package
RUN pip install standard-aifc

# Copy the rest of the application files into the container
COPY . .

# Expose the API port
EXPOSE 8000

# Command to run the FastAPI app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
