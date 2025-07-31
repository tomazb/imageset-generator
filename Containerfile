FROM node:18-alpine AS frontend-builder

# Build frontend
WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies with legacy peer deps to handle version conflicts
RUN npm install --legacy-peer-deps

# Copy source code
COPY frontend/ ./

# Build the application
RUN npm run build

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    wget \
    tar \
    libgpgme11 \
    libassuan0 \
    libdevmapper1.02.1 \
    && rm -rf /var/lib/apt/lists/*

# Download and install oc-mirror tool
RUN wget https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/latest-4.18/oc-mirror.tar.gz \
    && tar -xzf oc-mirror.tar.gz \
    && chmod +x oc-mirror \
    && mv oc-mirror /usr/local/bin/ \
    && rm oc-mirror.tar.gz

# Copy Python requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Make startup script executable
RUN chmod +x startup.sh

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Run the application
CMD ["./startup.sh"]
