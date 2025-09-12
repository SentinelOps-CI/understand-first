FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy dashboard code
COPY . .

# Create templates directory if it doesn't exist
RUN mkdir -p templates

# Make executable
RUN chmod +x dashboard_server.py

# Expose port
EXPOSE 5000

# Run the dashboard server
CMD ["python", "dashboard_server.py"]
