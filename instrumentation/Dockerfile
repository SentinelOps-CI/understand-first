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

# Copy instrumentation code
COPY . .

# Create templates directory if it doesn't exist
RUN mkdir -p templates

# Make executable
RUN chmod +x understand_first_metrics.py metrics_dashboard.py

# Expose port
EXPOSE 5001

# Run the metrics dashboard
CMD ["python", "metrics_dashboard.py"]
