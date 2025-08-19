import re

# Read the current app.py file
with open('app.py', 'r') as f:
    content = f.read()

# Find and replace the section in get_ocp_channels function
old_pattern = r'''        # Handle the case where version is None \(from /api/versions endpoint\)
        if version is None:
            # Return all available versions or a default response
            return jsonify\(\{
                "status": "success",
                "message": "Available OCP releases from static file",
                "available_versions": \[.*?\],
                "timestamp": datetime\.now\(\)\.isoformat\(\)
            \}\)'''

new_code = '''        # Handle the case where version is None (from /api/versions endpoint)
        if version is None:
            # Try to load from static file first
            try:
                static_file_path = os.path.join("data", "ocp-versions.json")
                if os.path.exists(static_file_path):
                    with open(static_file_path, 'r') as f:
                        data = json.load(f)
                        releases = data.get("releases", [])
                        return jsonify({
                            "status": "success",
                            "message": "Available OCP releases from static file",
                            "releases": releases,
                            "available_versions": releases,
                            "count": data.get("count", len(releases)),
                            "source": data.get("source", "static_file"),
                            "timestamp": datetime.now().isoformat()
                        })
            except Exception as e:
                app.logger.warning(f"Could not load static OCP versions file: {e}")
            
            # Fallback to hardcoded values if file doesn't exist or can't be read
            fallback_releases = ["4.20", "4.19", "4.18", "4.17", "4.16", "4.15", "4.14", "4.13", "4.12", "4.11", "4.10"]
            return jsonify({
                "status": "success",
                "message": "Available OCP releases (fallback)",
                "releases": fallback_releases,
                "available_versions": fallback_releases,
                "count": len(fallback_releases),
                "source": "fallback",
                "timestamp": datetime.now().isoformat()
            })'''

# Replace the pattern
updated_content = re.sub(old_pattern, new_code, content, flags=re.DOTALL)

# Write back to file
with open('app.py', 'w') as f:
    f.write(updated_content)

print("Updated get_ocp_channels function to read from static file")
