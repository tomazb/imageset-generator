#!/bin/bash

echo "Checking OCP release connectivity via Cincinnati API..."
echo "================================"

# Connectivity check against Cincinnati API (using python since curl is not in ubi-minimal)
timeout 15 python3.11 -c "
import urllib.request
req = urllib.request.Request(
    'https://api.openshift.com/api/upgrades_info/v1/graph?channel=stable-4.18&arch=amd64',
    headers={'Accept': 'application/json'}
)
urllib.request.urlopen(req, timeout=10)
" && {
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
