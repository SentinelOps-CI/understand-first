FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy commenter code
COPY understand_first_commenter.py .

# Make executable
RUN chmod +x understand_first_commenter.py

# Create entrypoint script
RUN echo '#!/bin/bash\npython understand_first_commenter.py "$@"' > entrypoint.sh && \
    chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
