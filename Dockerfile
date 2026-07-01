# Use the exact Python version requested
FROM python:3.11.15-slim

# Prevent Python from writing .pyc files and force stdout to be unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy dependency requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code (server.py, core.py, etc.)
COPY . .

# Create the downloads directory and ensure the app has write permissions
RUN mkdir -p downloads && chmod 777 downloads

# Expose the default port used by your server
EXPOSE 8008

# Command to run the server
CMD ["python", "server.py"]