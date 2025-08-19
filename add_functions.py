# Read the current app.py file
with open('app.py', 'r') as f:
    content = f.read()

# Define the functions to add
functions_to_add = '''

def load_operators_from_file(catalog_key, version_key):
    """Load operators from cached JSON files"""
    try:
        # Define file patterns for different catalog types
        file_patterns = {
            'redhat': f'operators-redhat-{version_key}.json',
            'community': f'operators-community-{version_key}.json',
            'certified': f'operators-certified-{version_key}.json',
            'marketplace': f'operators-marketplace-{version_key}.json'
        }
        
        filename = file_patterns.get(catalog_key, f'operators-{catalog_key}-{version_key}.json')
        filepath = os.path.join('data', filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                return data.get('operators', [])
        
        return None
        
    except Exception as e:
        app.logger.error(f"Error loading operators from file: {e}")
        return None


def load_catalogs_from_file(version_key):
    """Load catalog information from cached JSON files"""
    try:
        filename = f'catalogs-{version_key}.json'
        filepath = os.path.join('data', filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                catalogs = json.load(f)
                return catalogs
        
        return None
        
    except Exception as e:
        app.logger.error(f"Error loading catalogs from file: {e}")
        return None

'''

# Find the place to insert the functions (after CORS line)
cors_line = "CORS(app)  # Enable CORS for all routes"
insertion_point = content.find(cors_line)
if insertion_point != -1:
    insertion_point = content.find('\n', insertion_point) + 1
    new_content = content[:insertion_point] + functions_to_add + content[insertion_point:]
    
    # Write the updated content
    with open('app.py', 'w') as f:
        f.write(new_content)
    
    print("Functions added successfully")
else:
    print("Could not find insertion point")
