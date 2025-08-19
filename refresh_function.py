def refresh_versions():
    """Refresh the list of available OCP releases"""
    try:
        import subprocess
        import json
        import re
        import os
        from datetime import datetime
        
        app.logger.info("Starting OCP releases refresh using oc-mirror...")
        
        # Run oc-mirror list releases command
        result = subprocess.run(
            ['oc-mirror', 'list', 'releases'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            app.logger.error(f"oc-mirror command failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'message': f'oc-mirror command failed: {result.stderr}',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Parse the output to extract version numbers
        releases = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            # Skip empty lines, warnings, and headers
            if (line and 
                not line.startswith('⚠️') and 
                not line.startswith('W') and
                not line.startswith('I') and
                not line.startswith('Listing') and
                not line.startswith('#') and
                not line.startswith('Available')):
                
                # Match version patterns like 4.16, 4.17, etc.
                if re.match(r'^\d+\.\d+$', line):
                    if line not in releases:
                        releases.append(line)
        
        # Sort releases in reverse order (newest first)
        releases.sort(key=lambda x: tuple(map(int, x.split('.'))), reverse=True)
        
        # Prepare data structure
        ocp_data = {
            "releases": releases,
            "count": len(releases),
            "source": "oc-mirror",
            "timestamp": datetime.now().isoformat(),
            "command": "oc-mirror list releases"
        }
        
        # Ensure data directory exists
        data_dir = "data"
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        # Write to ocp-versions.json file
        output_file = os.path.join(data_dir, "ocp-versions.json")
        with open(output_file, 'w') as f:
            json.dump(ocp_data, f, indent=2)
        
        app.logger.info(f"Successfully refreshed {len(releases)} OCP releases to {output_file}")
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully refreshed {len(releases)} OCP releases',
            'releases': releases,
            'count': len(releases),
            'file': output_file,
            'timestamp': datetime.now().isoformat()
        })
        
    except subprocess.TimeoutExpired:
        app.logger.error("oc-mirror command timed out")
        return jsonify({
            'status': 'error',
            'message': 'oc-mirror command timed out (60 seconds)',
            'timestamp': datetime.now().isoformat()
        }), 504
    except FileNotFoundError:
        app.logger.error("oc-mirror command not found")
        return jsonify({
            'status': 'error',
            'message': 'oc-mirror command not found. Please ensure oc-mirror is installed and available in PATH.',
            'timestamp': datetime.now().isoformat()
        }), 500
    except Exception as e:
        app.logger.error(f"Error refreshing OCP releases: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error refreshing OCP releases: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500
