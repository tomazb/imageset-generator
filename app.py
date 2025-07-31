#!/usr/bin/env python3
"""
OpenShift ImageSetConfiguration Generator - Flask API Backend

This Flask application provides a REST API for the OpenShift ImageSetConfiguration generator.
It serves as the backend for the React frontend application.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yaml
import os
import tempfile
from datetime import datetime
from generator import ImageSetGenerator
import traceback

app = Flask(__name__, static_folder='frontend/build')
CORS(app)  # Enable CORS for all routes


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    """Serve React app"""
    # Don't interfere with static files or API routes
    if path.startswith('static/') or path.startswith('api/'):
        return app.send_static_file(path) if path.startswith('static/') else None
    
    # For all other paths, check if the file exists in static folder
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })



@app.route('/api/releases', methods=['GET'])
def get_ocp_releases():
    """Get available OCP releases using oc-mirror list releases command"""
    try:
        import subprocess
        import re
        
        # Run oc-mirror list releases command
        result = subprocess.run(
            ['oc-mirror', 'list', 'releases'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # Parse the output and extract version numbers
            releases = []
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                # Skip the header line and empty lines
                if (line and 
                    not line.startswith('Available OpenShift') and
                    not line.startswith('Available') and
                    # Look for version patterns like 4.X
                    re.match(r'^\d+\.\d+', line)):
                    
                    # Extract the version
                    version_match = re.match(r'^(\d+\.\d+)', line)
                    if version_match:
                        version = version_match.group(1)
                        if version not in releases:
                            releases.append(version)
            
            # Sort releases in descending order (newest first)
            releases = sorted(list(set(releases)), key=lambda x: [int(i) for i in x.split('.')], reverse=True)
            
            if releases:
                return jsonify({
                    'status': 'success',
                    'releases': releases,
                    'count': len(releases),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oc-mirror command',
                    'note': 'Releases fetched dynamically from oc-mirror'
                })
            else:
                raise Exception("No releases found in oc-mirror output")
        else:
            raise Exception(f"oc-mirror command failed with return code {result.returncode}: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("Warning: oc-mirror list releases command timed out, using fallback list")
        pass
    except FileNotFoundError:
        print("Warning: oc-mirror command not found, using fallback list")
        pass
    except Exception as e:
        print(f"Warning: Error running oc-mirror list releases: {str(e)}, using fallback list")
        pass
    
    # Fallback to static list
    fallback_releases = ['4.18', '4.17', '4.16', '4.15', '4.14', '4.13', '4.12', '4.11', '4.10', '4.9', '4.8', '4.7', '4.6']
    return jsonify({
        'status': 'success',
        'releases': fallback_releases,
        'count': len(fallback_releases),
        'timestamp': datetime.now().isoformat(),
        'source': 'static fallback',
        'note': 'Using fallback release list - oc-mirror command not available or failed'
    })


@app.route('/api/channels/<version>', methods=['GET'])
def get_ocp_channels(version):
    """Get available OCP channels for a specific version using oc-mirror"""
    try:
        import subprocess
        import re
        
        # Validate version format (basic validation)
        if not re.match(r'^\d+\.\d+$', version):
            return jsonify({
                'status': 'error',
                'message': 'Invalid version format. Expected format: X.Y (e.g., 4.14)',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        # Run oc-mirror list releases --channels --version=X.Y command
        result = subprocess.run(
            ['oc-mirror', 'list', 'releases', '--channels', f'--version={version}'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Parse the output and extract channel names
            channels = []
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                # Skip empty lines, warnings, and header text
                if (line and 
                    not line.startswith('⚠️') and 
                    not line.startswith('W') and
                    not line.startswith('Listing channels') and
                    not line.startswith('#') and
                    # Check if line looks like a channel name (contains numbers and hyphens)
                    re.match(r'^[a-z]+-\d+\.\d+$', line)):
                    channels.append(line)
            
            # Remove duplicates and sort
            channels = sorted(list(set(channels)))
            
            return jsonify({
                'status': 'success',
                'version': version,
                'channels': channels,
                'count': len(channels),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to fetch channels',
                'error': result.stderr,
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'status': 'error',
            'message': 'Request timeout while fetching channels',
            'timestamp': datetime.now().isoformat()
        }), 504
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error fetching channels: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/releases/<channel>', methods=['GET'])
def get_channel_releases(channel):
    """Get available releases for a specific channel using oc-mirror"""
    try:
        # Validate channel parameter
        if not channel or not channel.strip():
            return jsonify({
                'status': 'error',
                'error': 'Channel parameter is required'
            }), 400
        
        import subprocess
        import re
        
        # Run oc-mirror list releases --channel=<channel> command
        result = subprocess.run(
            ['oc-mirror', 'list', 'releases', f'--channel={channel}'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({
                'status': 'error',
                'error': f'oc-mirror command failed: {result.stderr}'
            }), 500
        
        # Parse the output to extract releases
        releases = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            # Look for version patterns like 4.16.0, 4.18.1, etc.
            if re.match(r'^\d+\.\d+\.\d+$', line):
                releases.append(line)
        
        # Sort releases in semantic version order
        releases.sort(key=lambda x: tuple(map(int, x.split('.'))))
        
        return jsonify({
            'status': 'success',
            'channel': channel,
            'releases': releases,
            'count': len(releases)
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({
            'status': 'error',
            'error': 'Command timed out'
        }), 504
    except Exception as e:
        app.logger.error(f"Error getting channel releases: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/operators/mappings', methods=['GET'])
def get_operator_mappings():
    """Get available operator mappings"""
    # Extract operator mappings from generator
    operator_mappings = {
        "logging": "cluster-logging",
        "logging-operator": "cluster-logging", 
        "monitoring": "cluster-monitoring-operator",
        "cluster-monitoring": "cluster-monitoring-operator",
        "service-mesh": "servicemeshoperator",
        "istio": "servicemeshoperator",
        "serverless": "serverless-operator",
        "knative": "serverless-operator",
        "pipelines": "openshift-pipelines-operator-rh",
        "tekton": "openshift-pipelines-operator-rh",
        "gitops": "openshift-gitops-operator",
        "argocd": "openshift-gitops-operator",
        "storage": "odf-operator",
        "ocs": "odf-operator",
        "ceph": "odf-operator",
        "elasticsearch": "elasticsearch-operator",
        "jaeger": "jaeger-product",
        "kiali": "kiali-ossm"
    }
    
    return jsonify({
        'mappings': operator_mappings,
        'suggestions': list(operator_mappings.keys())
    })


@app.route('/api/operators/catalogs/<version>', methods=['GET'])
def get_operator_catalogs(version):
    """Get operator catalog URL for a specific OCP version"""
    try:
        # Extract major.minor version from version string
        if '.' in version:
            version_parts = version.split('.')
            major = version_parts[0]
            minor = version_parts[1]
            version_key = f"{major}.{minor}"
        else:
            version_key = version
        
        # Define operator catalog mappings by OCP version
        catalog_mappings = {
            "4.30": "registry.redhat.io/redhat/redhat-operator-index:v4.30",
            "4.29": "registry.redhat.io/redhat/redhat-operator-index:v4.29",
            "4.28": "registry.redhat.io/redhat/redhat-operator-index:v4.28",
            "4.27": "registry.redhat.io/redhat/redhat-operator-index:v4.27",
            "4.26": "registry.redhat.io/redhat/redhat-operator-index:v4.26",
            "4.25": "registry.redhat.io/redhat/redhat-operator-index:v4.25",
            "4.24": "registry.redhat.io/redhat/redhat-operator-index:v4.24",
            "4.23": "registry.redhat.io/redhat/redhat-operator-index:v4.23",
            "4.22": "registry.redhat.io/redhat/redhat-operator-index:v4.22",
            "4.21": "registry.redhat.io/redhat/redhat-operator-index:v4.21",
            "4.20": "registry.redhat.io/redhat/redhat-operator-index:v4.20",
            "4.19": "registry.redhat.io/redhat/redhat-operator-index:v4.19", 
            "4.18": "registry.redhat.io/redhat/redhat-operator-index:v4.18",
            "4.17": "registry.redhat.io/redhat/redhat-operator-index:v4.17",
            "4.16": "registry.redhat.io/redhat/redhat-operator-index:v4.16",
            "4.15": "registry.redhat.io/redhat/redhat-operator-index:v4.15",
            "4.14": "registry.redhat.io/redhat/redhat-operator-index:v4.14",
            "4.13": "registry.redhat.io/redhat/redhat-operator-index:v4.13",
            "4.12": "registry.redhat.io/redhat/redhat-operator-index:v4.12",
            "4.11": "registry.redhat.io/redhat/redhat-operator-index:v4.11",
            "4.10": "registry.redhat.io/redhat/redhat-operator-index:v4.10",
            "4.9": "registry.redhat.io/redhat/redhat-operator-index:v4.9",
            "4.8": "registry.redhat.io/redhat/redhat-operator-index:v4.8",
            "4.7": "registry.redhat.io/redhat/redhat-operator-index:v4.7",
            "4.6": "registry.redhat.io/redhat/redhat-operator-index:v4.6",
            "4.5": "registry.redhat.io/redhat/redhat-operator-index:v4.5",
            "4.4": "registry.redhat.io/redhat/redhat-operator-index:v4.4",
            "4.3": "registry.redhat.io/redhat/redhat-operator-index:v4.3",
            "4.2": "registry.redhat.io/redhat/redhat-operator-index:v4.2",
            "4.1": "registry.redhat.io/redhat/redhat-operator-index:v4.1",
            "4.0": "registry.redhat.io/redhat/redhat-operator-index:v4.0"
        }
        
        # Get catalog URL or default to latest
        catalog_url = catalog_mappings.get(version_key, "registry.redhat.io/redhat/redhat-operator-index")
        
        return jsonify({
            'status': 'success',
            'version': version,
            'catalog': catalog_url,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error getting operator catalog for version {version}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get operator catalog: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/operators/catalogs', methods=['GET'])
def get_available_catalogs():
    """Get all available operator catalogs using oc-mirror"""
    try:
        import subprocess
        
        # Define standard catalog URLs to check
        standard_catalogs = [
            {
                "name": "Red Hat Operators",
                "url": "registry.redhat.io/redhat/redhat-operator-index",
                "description": "Official Red Hat certified operators"
            },
            {
                "name": "Community Operators", 
                "url": "registry.redhat.io/redhat/community-operator-index",
                "description": "Community-maintained operators"
            },
            {
                "name": "Certified Operators",
                "url": "registry.redhat.io/redhat/certified-operator-index", 
                "description": "Third-party certified operators"
            },
            {
                "name": "Red Hat Marketplace",
                "url": "registry.redhat.io/redhat/redhat-marketplace-index",
                "description": "Commercial operators from Red Hat Marketplace"
            }
        ]
        
        validated_catalogs = []
        
        # Try to validate each catalog with oc-mirror
        for catalog in standard_catalogs:
            try:
                # Test if oc-mirror can access this catalog
                cmd = ['oc-mirror', 'list', 'operators', '--catalogs', catalog['url']]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                
                catalog_info = catalog.copy()
                if result.returncode == 0:
                    catalog_info['validated'] = True
                    app.logger.info(f"Validated catalog: {catalog['url']}")
                else:
                    catalog_info['validated'] = False
                    app.logger.warning(f"Could not validate catalog: {catalog['url']}")
                
                validated_catalogs.append(catalog_info)
                
            except subprocess.TimeoutExpired:
                catalog_info = catalog.copy()
                catalog_info['validated'] = False
                catalog_info['error'] = 'Timeout while validating'
                validated_catalogs.append(catalog_info)
                app.logger.warning(f"Timeout validating catalog: {catalog['url']}")
                
            except Exception as e:
                catalog_info = catalog.copy()
                catalog_info['validated'] = False
                catalog_info['error'] = str(e)
                validated_catalogs.append(catalog_info)
                app.logger.warning(f"Error validating catalog {catalog['url']}: {e}")
        
        return jsonify({
            'status': 'success',
            'catalogs': validated_catalogs,
            'count': len(validated_catalogs),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error getting available catalogs: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get available catalogs: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/operators/catalogs/<version>/list', methods=['GET'])
def list_catalogs_for_version(version):
    """Use oc-mirror to list available catalogs for a specific OCP version"""
    try:
        import subprocess
        
        # Extract major.minor version from version string
        if '.' in version:
            version_parts = version.split('.')
            major = version_parts[0]
            minor = version_parts[1]
            version_key = f"{major}.{minor}"
        else:
            version_key = version
        
        # Define base catalog URLs to test with this version
        base_catalogs = [
            {
                "name": "Red Hat Operators",
                "base_url": "registry.redhat.io/redhat/redhat-operator-index",
                "description": "Official Red Hat certified operators",
                "default": True
            },
            {
                "name": "Community Operators",
                "base_url": "registry.redhat.io/redhat/community-operator-index",
                "description": "Community-maintained operators",
                "default": False
            },
            {
                "name": "Certified Operators", 
                "base_url": "registry.redhat.io/redhat/certified-operator-index",
                "description": "Third-party certified operators",
                "default": False
            },
            {
                "name": "Red Hat Marketplace",
                "base_url": "registry.redhat.io/redhat/redhat-marketplace-index",
                "description": "Commercial operators from Red Hat Marketplace",
                "default": False
            }
        ]
        
        available_catalogs = []
        
        for catalog in base_catalogs:
            # Create versioned catalog URL
            versioned_url = f"{catalog['base_url']}:v{version_key}"
            
            catalog_info = {
                "name": catalog['name'],
                "url": versioned_url,
                "description": f"{catalog['description']} for OCP {version_key}",
                "default": catalog['default'],
                "validated": False,
                "operators_count": 0
            }
            
            try:
                # Use oc-mirror to validate and get operator count for this catalog
                app.logger.info(f"Checking catalog {versioned_url} with oc-mirror...")
                cmd = ['oc-mirror', 'list', 'operators', '--catalogs', versioned_url, '--version', version_key]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    catalog_info['validated'] = True
                    
                    # Try to parse operator count from output
                    lines = result.stdout.strip().split('\n')
                    operator_lines = [line for line in lines if line.strip() and not line.startswith('#') and not line.startswith('WARN') and not line.startswith('INFO')]
                    catalog_info['operators_count'] = len(operator_lines)
                    
                    app.logger.info(f"Successfully validated {versioned_url} with {catalog_info['operators_count']} operators")
                else:
                    app.logger.warning(f"oc-mirror failed for {versioned_url}: {result.stderr}")
                    catalog_info['error'] = result.stderr.strip() if result.stderr else 'Unknown error'
                
            except subprocess.TimeoutExpired:
                app.logger.warning(f"Timeout while checking {versioned_url}")
                catalog_info['error'] = 'Timeout while validating'
                
            except Exception as e:
                app.logger.warning(f"Error checking {versioned_url}: {e}")
                catalog_info['error'] = str(e)
            
            available_catalogs.append(catalog_info)
        
        # Sort catalogs by validation status and operator count
        available_catalogs.sort(key=lambda x: (not x['validated'], -x['operators_count'], x['name']))
        
        return jsonify({
            'status': 'success',
            'version': version,
            'catalogs': available_catalogs,
            'count': len(available_catalogs),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error listing catalogs for version {version}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to list catalogs: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/operators/catalogs/<version>/discover', methods=['GET'])
def discover_catalogs_for_version(version):
    """Discover available operator catalogs dynamically using oc-mirror"""
    try:
        import subprocess
        
        # Extract major.minor version from version string
        if '.' in version:
            version_parts = version.split('.')
            major = version_parts[0]
            minor = version_parts[1]
            version_key = f"{major}.{minor}"
        else:
            version_key = version
        
        discovered_catalogs = []
        
        try:
            # First, try to discover what catalogs are available by running oc-mirror help
            # or by checking known registry endpoints
            app.logger.info(f"Discovering catalogs for OCP version {version_key}...")
            
            # Try some common catalog discovery approaches
            discovery_commands = [
                # Try to list available catalogs (this might not work in all oc-mirror versions)
                ['oc-mirror', 'list', 'operators', '--help'],
            ]
            
            # Since oc-mirror doesn't have a direct catalog discovery command,
            # we'll use a heuristic approach to test known registry patterns
            common_registries = [
                "registry.redhat.io/redhat",
                "quay.io/operatorhubio", 
                "registry.connect.redhat.com"
            ]
            
            common_catalog_types = [
                "redhat-operator-index",
                "community-operator-index", 
                "certified-operator-index",
                "redhat-marketplace-index"
            ]
            
            for registry in common_registries:
                for catalog_type in common_catalog_types:
                    catalog_url = f"{registry}/{catalog_type}:v{version_key}"
                    
                    try:
                        # Test if this catalog exists and contains operators
                        cmd = ['oc-mirror', 'list', 'operators', '--catalogs', catalog_url, '--version', version_key]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                        
                        if result.returncode == 0:
                            # Parse the output to count operators
                            lines = result.stdout.strip().split('\n')
                            operator_lines = [line for line in lines if line.strip() and 
                                            not line.startswith('#') and 
                                            not line.startswith('WARN') and 
                                            not line.startswith('INFO') and
                                            not line.startswith('Error') and
                                            not line.startswith('Failed')]
                            
                            if len(operator_lines) > 0:
                                catalog_info = {
                                    "name": catalog_type.replace('-', ' ').title(),
                                    "url": catalog_url,
                                    "description": f"Operators from {registry}/{catalog_type}",
                                    "validated": True,
                                    "operators_count": len(operator_lines),
                                    "registry": registry,
                                    "default": catalog_type == "redhat-operator-index" and registry == "registry.redhat.io/redhat"
                                }
                                
                                discovered_catalogs.append(catalog_info)
                                app.logger.info(f"Discovered catalog: {catalog_url} with {len(operator_lines)} operators")
                        
                    except subprocess.TimeoutExpired:
                        app.logger.debug(f"Timeout testing catalog: {catalog_url}")
                        continue
                    except Exception as e:
                        app.logger.debug(f"Error testing catalog {catalog_url}: {e}")
                        continue
            
            # Sort by operator count (descending) and then by name
            discovered_catalogs.sort(key=lambda x: (-x['operators_count'], x['name']))
            
            return jsonify({
                'status': 'success',
                'version': version,
                'catalogs': discovered_catalogs,
                'count': len(discovered_catalogs),
                'discovery_method': 'oc-mirror_heuristic',
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            app.logger.error(f"Error during catalog discovery: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Catalog discovery failed: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }), 500
        
    except Exception as e:
        app.logger.error(f"Error discovering catalogs for version {version}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to discover catalogs: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/operators/list', methods=['GET'])
def get_operators_list():
    """Get list of available operators from a catalog using oc-mirror"""
    try:
        import subprocess
        
        # Get parameters from query string
        catalog = request.args.get('catalog', 'registry.redhat.io/redhat/redhat-operator-index')
        version = request.args.get('version', '4.18')
        
        # Extract major.minor version from version string
        if '.' in version:
            version_parts = version.split('.')
            major = version_parts[0]
            minor = version_parts[1]
            version_key = f"{major}.{minor}"
        else:
            version_key = version
        
        # Create versioned catalog URL if not already versioned
        if ':v' not in catalog:
            catalog_url = f"{catalog}:v{version_key}"
        else:
            catalog_url = catalog
        
        app.logger.info(f"Fetching operators from catalog {catalog_url} for version {version_key}")
        
        # Run oc-mirror command to list operators
        cmd = ['oc-mirror', 'list', 'operators', '--catalogs', catalog_url, '--version', version_key]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            app.logger.error(f"oc-mirror failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to fetch operators: {result.stderr}',
                'timestamp': datetime.utcnow().isoformat()
            }), 500
        
        # Parse the output to extract operator information
        operators = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            # Skip empty lines, warnings, and headers
            if (line and 
                not line.startswith('#') and 
                not line.startswith('WARN') and 
                not line.startswith('INFO') and
                not line.startswith('Error') and
                not line.startswith('Failed') and
                not line.startswith('Listing') and
                not line.startswith('Using')):
                
                # Try to parse operator information
                # oc-mirror output format can vary, but typically includes operator name
                parts = line.split()
                if len(parts) >= 1:
                    operator_name = parts[0]
                    
                    # Extract additional info if available (channel, version, etc.)
                    operator_info = {
                        'name': operator_name,
                        'display_name': operator_name.replace('-', ' ').title(),
                        'description': f'Operator from {catalog_url}',
                        'catalog': catalog_url,
                        'version': version_key
                    }
                    
                    # Try to extract channel information if present
                    if len(parts) >= 2:
                        operator_info['default_channel'] = parts[1]
                    
                    operators.append(operator_info)
        
        # Remove duplicates and sort by name
        unique_operators = {}
        for op in operators:
            if op['name'] not in unique_operators:
                unique_operators[op['name']] = op
        
        sorted_operators = sorted(unique_operators.values(), key=lambda x: x['name'])
        
        app.logger.info(f"Found {len(sorted_operators)} operators in catalog {catalog_url}")
        
        return jsonify({
            'status': 'success',
            'catalog': catalog_url,
            'version': version_key,
            'operators': sorted_operators,
            'count': len(sorted_operators),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except subprocess.TimeoutExpired:
        app.logger.error("Timeout while fetching operators")
        return jsonify({
            'status': 'error',
            'message': 'Request timeout while fetching operators',
            'timestamp': datetime.utcnow().isoformat()
        }), 504
    except Exception as e:
        app.logger.error(f"Error fetching operators: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch operators: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/operators/<operator_name>/channels', methods=['GET'])
def get_operator_channels(operator_name):
    """Get available channels for a specific operator using oc-mirror"""
    try:
        import subprocess
        
        # Get parameters from query string
        catalog = request.args.get('catalog', 'registry.redhat.io/redhat/redhat-operator-index')
        version = request.args.get('version', '4.18')
        
        # Extract major.minor version from version string
        if '.' in version:
            version_parts = version.split('.')
            major = version_parts[0]
            minor = version_parts[1]
            version_key = f"{major}.{minor}"
        else:
            version_key = version
        
        # Create versioned catalog URL if not already versioned
        if ':v' not in catalog:
            catalog_url = f"{catalog}:v{version_key}"
        else:
            catalog_url = catalog
        
        app.logger.info(f"Fetching channels for operator {operator_name} from {catalog_url}")
        
        # Run oc-mirror command to list operator details
        cmd = ['oc-mirror', 'list', 'operators', '--catalogs', catalog_url, '--version', version_key, operator_name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            app.logger.warning(f"oc-mirror failed for operator channels: {result.stderr}")
            # Return default channel structure if command fails
            return jsonify({
                'status': 'success',
                'operator': operator_name,
                'catalog': catalog_url,
                'channels': [{'name': 'stable', 'default': True}],
                'default_channel': 'stable',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Parse the output to extract channel information
        channels = []
        default_channel = 'stable'
        
        lines = result.stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            # Look for channel information in the output
            if 'channel' in line.lower() or 'stable' in line or 'fast' in line or 'alpha' in line or 'beta' in line:
                # Extract channel names
                parts = line.split()
                for part in parts:
                    if part in ['stable', 'fast', 'alpha', 'beta'] or '-' in part:
                        channel_info = {
                            'name': part,
                            'default': part == 'stable'
                        }
                        if channel_info not in channels:
                            channels.append(channel_info)
        
        # If no channels found, provide defaults
        if not channels:
            channels = [
                {'name': 'stable', 'default': True},
                {'name': 'fast', 'default': False}
            ]
        
        return jsonify({
            'status': 'success',
            'operator': operator_name,
            'catalog': catalog_url,
            'channels': channels,
            'default_channel': default_channel,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({
            'status': 'error',
            'message': 'Request timeout while fetching operator channels',
            'timestamp': datetime.utcnow().isoformat()
        }), 504
    except Exception as e:
        app.logger.error(f"Error fetching operator channels: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch operator channels: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/generate/preview', methods=['POST'])
def generate_preview():
    """Generate YAML preview without saving"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Create generator instance
        generator = ImageSetGenerator()
        
        # Add OCP versions
        if data.get('ocp_versions') or data.get('ocp_min_version') or data.get('ocp_max_version'):
            # New approach with min/max versions
            channel = data.get('ocp_channel', 'stable-4.14')
            min_version = data.get('ocp_min_version')
            max_version = data.get('ocp_max_version')
            
            # Support legacy versions list for backward compatibility
            legacy_versions = None
            if data.get('ocp_versions'):
                legacy_versions = [v.strip() for v in data['ocp_versions'] if v.strip()]
            
            generator.add_ocp_versions(
                versions=legacy_versions,
                channel=channel,
                min_version=min_version,
                max_version=max_version
            )
        
        # Add operators
        if data.get('operators'):
            operators = [op.strip() for op in data['operators'] if op.strip()]
            
            # Handle multiple catalogs (new format) or single catalog (backward compatibility)
            catalogs = data.get('operator_catalogs', [])
            if not catalogs and data.get('operator_catalog'):
                catalogs = [data.get('operator_catalog')]
            if not catalogs:
                catalogs = ['registry.redhat.io/redhat/redhat-operator-index']
            
            # Add operators for each catalog
            for catalog in catalogs:
                generator.add_operators(operators, catalog.strip())
        
        # Add additional images
        if data.get('additional_images'):
            images = [img.strip() for img in data['additional_images'] if img.strip()]
            generator.add_additional_images(images)
        
        # Add helm charts
        if data.get('helm_charts'):
            generator.add_helm_charts(data['helm_charts'])
        
        # Set KubeVirt container mirroring
        if data.get('kubevirt_container', False):
            generator.set_kubevirt_container(True)
        
        # Generate YAML
        yaml_content = generator.generate_yaml()
        
        return jsonify({
            'success': True,
            'yaml': yaml_content,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error generating preview: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'error': f'Failed to generate preview: {str(e)}',
            'success': False
        }), 500


@app.route('/api/generate/download', methods=['POST'])
def generate_download():
    """Generate and return downloadable YAML file"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Create generator instance
        generator = ImageSetGenerator()
        
        # Add OCP versions
        if data.get('ocp_versions') or data.get('ocp_min_version') or data.get('ocp_max_version'):
            # New approach with min/max versions
            channel = data.get('ocp_channel', 'stable-4.14')
            min_version = data.get('ocp_min_version')
            max_version = data.get('ocp_max_version')
            
            # Support legacy versions list for backward compatibility
            legacy_versions = None
            if data.get('ocp_versions'):
                legacy_versions = [v.strip() for v in data['ocp_versions'] if v.strip()]
            
            generator.add_ocp_versions(
                versions=legacy_versions,
                channel=channel,
                min_version=min_version,
                max_version=max_version
            )
        
        # Add operators
        if data.get('operators'):
            operators = [op.strip() for op in data['operators'] if op.strip()]
            
            # Handle multiple catalogs (new format) or single catalog (backward compatibility)
            catalogs = data.get('operator_catalogs', [])
            if not catalogs and data.get('operator_catalog'):
                catalogs = [data.get('operator_catalog')]
            if not catalogs:
                catalogs = ['registry.redhat.io/redhat/redhat-operator-index']
            
            # Add operators for each catalog
            for catalog in catalogs:
                generator.add_operators(operators, catalog.strip())
        
        # Add additional images
        if data.get('additional_images'):
            images = [img.strip() for img in data['additional_images'] if img.strip()]
            generator.add_additional_images(images)
        
        # Add helm charts
        if data.get('helm_charts'):
            generator.add_helm_charts(data['helm_charts'])
        
        # Set KubeVirt container mirroring
        if data.get('kubevirt_container', False):
            generator.set_kubevirt_container(True)
        
        # Generate YAML
        yaml_content = generator.generate_yaml()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(yaml_content)
            temp_filename = temp_file.name
        
        # Return file content for download
        response = app.response_class(
            yaml_content,
            mimetype='application/x-yaml',
            headers={
                'Content-Disposition': f'attachment; filename=imageset-config.yaml'
            }
        )
        
        # Clean up temp file
        try:
            os.unlink(temp_filename)
        except:
            pass
        
        return response
        
    except Exception as e:
        app.logger.error(f"Error generating download: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'error': f'Failed to generate download: {str(e)}',
            'success': False
        }), 500


@app.route('/api/validate', methods=['POST'])
def validate_config():
    """Validate configuration data"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        errors = []
        warnings = []
        
        # Check if at least one configuration is provided
        has_ocp = bool(data.get('ocp_versions'))
        has_operators = bool(data.get('operators'))
        has_images = bool(data.get('additional_images'))
        has_helm = bool(data.get('helm_charts'))
        
        if not (has_ocp or has_operators or has_images or has_helm):
            errors.append('At least one configuration section must be specified (OCP versions, operators, additional images, or Helm charts)')
        
        # Validate OCP versions format
        if has_ocp:
            for version in data.get('ocp_versions', []):
                if not version.strip():
                    continue
                version_parts = version.strip().split('.')
                if len(version_parts) < 3 or not all(part.isdigit() for part in version_parts[:3]):
                    warnings.append(f'OCP version "{version}" may not be in the expected format (e.g., 4.14.1)')
        
        # Validate operator catalog URL
        if data.get('operator_catalog'):
            catalog = data.get('operator_catalog')
            if not catalog.startswith(('http://', 'https://', 'registry.')):
                warnings.append('Operator catalog should be a valid registry URL')
        
        # Validate additional images
        if has_images:
            for image in data.get('additional_images', []):
                if not image.strip():
                    continue
                if ':' not in image:
                    warnings.append(f'Image "{image}" may be missing a tag (e.g., :latest)')
        
        # Validate Helm charts
        if has_helm:
            for chart in data.get('helm_charts', []):
                if not chart.get('name'):
                    errors.append('Helm chart name is required')
                if not chart.get('repository'):
                    errors.append('Helm chart repository is required')
        
        return jsonify({
            'success': True,
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        })
        
    except Exception as e:
        app.logger.error(f"Error validating config: {str(e)}")
        return jsonify({
            'error': f'Failed to validate configuration: {str(e)}',
            'success': False
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors by serving React app"""
    return send_from_directory(app.static_folder, 'index.html')


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'success': False
    }), 500


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='OpenShift ImageSetConfiguration Generator Web API')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting OpenShift ImageSetConfiguration Generator Web API...")
    print(f"Access the application at: http://{args.host}:{args.port}")
    
    app.run(host=args.host, port=args.port, debug=args.debug)
