# Step 1: Start with an official Python image
FROM python:3.11-slim

# Step 2: Install system dependencies (portaudio and others)
RUN apt-get update && \
    apt-get install -y \
    portaudio19-dev \
    build-essential \
    libsndfile1 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*  # Clean up to reduce image size

# Step 3: Set the working directory in the container
WORKDIR /app

# Step 4: Copy the current directory contents into the container
COPY . /app

# Step 5: Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Step 6: Expose port for Flask app (default Flask port is 5000)
EXPOSE 5000

# Step 7: Set the command to run the app (for example, using gunicorn for production)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]
