#!/bin/bash

echo "Checking OCP release connectivity via Cincinnati API..."
echo "================================"

# Connectivity check against Cincinnati API
timeout 15 curl -sf "https://api.openshift.com/api/upgrades_info/v1/graph?channel=stable-4.18&arch=amd64" -H "Accept: application/json" -o /dev/null && {
    echo "Cincinnati API reachable"
} || {
    echo "Warning: Could not reach Cincinnati API (network issue or timeout)"
    echo "The application will continue without live release data"
}

echo "================================"
echo ""
echo "Starting OpenShift ImageSetConfiguration Generator Web API..."

# Start the Flask application using the new package structure
export PYTHONPATH="/app/src${PYTHONPATH:+:$PYTHONPATH}"
export IMAGESET_GENERATOR_ROOT="${IMAGESET_GENERATOR_ROOT:-/app}"
exec python3.11 -m imageset_generator.app --host 0.0.0.0 --port 5000
