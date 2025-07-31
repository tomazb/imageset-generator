# OpenShift ImageSetConfiguration Generator

This tool generates ImageSetConfiguration files for OpenShift disconnected installations using the oc-mirror tool. It takes OCP versions and operator suggestions as input and creates a YAML configuration that can be used to mirror container images and operators for air-gapped environments.

## Interfaces Available

- **Web UI (React + Flask)**: Modern web interface with tabs and real-time preview
- **Desktop GUI (Tkinter)**: Native desktop application with multiple tabs
- **Command Line**: Traditional CLI interface for scripting and automation

## Features

- Generate ImageSetConfiguration YAML files
- Support for multiple OCP versions and channels
- Smart operator name mapping (e.g., "logging" → "cluster-logging")
- Support for additional container images
- Helm chart mirroring configuration
- Multiple input methods (Web UI, GUI, CLI, configuration files)
- Real-time YAML preview
- Configuration file import/export
- Extensible operator mapping system

## Installation

### Prerequisites

- Python 3.8 or higher
- Node.js 16 or higher (for web interface)
- npm (for web interface)

### Quick Start

1. Clone or download this repository
2. For web interface:
   ```bash
   chmod +x start-web.sh
   ./start-web.sh
   ```
3. For containerized deployment:
   ```bash
   chmod +x start-podman.sh
   ./start-podman.sh
   ```
4. For desktop GUI:
   ```bash
   pip install -r requirements.txt
   python gui.py
   ```
5. For command line:
   ```bash
   pip install -r requirements.txt
   python generator.py --help
   ```

## Web Interface Usage

### Production Mode (Recommended)
```bash
./start-web.sh
```
Access at: http://localhost:5000

### Development Mode
```bash
./start-dev.sh
```
- Backend API: http://localhost:5000
- Frontend: http://localhost:3000

### Containerized Deployment (Podman)

```bash
./start-podman.sh
```
Access at: http://localhost:5000

### Development Mode (Podman)
```bash
./start-podman-dev.sh
```

### Manual Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install and build frontend
cd frontend
npm install
npm run build
cd ..

# Start the server
python app.py
```

## Desktop GUI Usage

```bash
pip install -r requirements.txt
python gui.py
```

The GUI provides:
- Tabbed interface for different configuration sections
- Drag-and-drop file loading
- Real-time form validation
- Built-in operator suggestions
- YAML preview and export

## Command Line Usage

### Basic Examples

Generate configuration with OCP versions and operators:
```bash
python generator.py --ocp-versions 4.14.1,4.14.2 --operators logging,monitoring,pipelines
```

Use configuration file:
```bash
python generator.py --config example-config.json
```

Custom output file:
```bash
python generator.py --ocp-versions 4.14.1 --operators logging --output my-imageset.yaml
```

### Advanced Examples

Specify custom operator catalog:
```bash
python generator.py --ocp-versions 4.14.1 --operators logging --operator-catalog registry.redhat.io/redhat/redhat-operator-index:v4.14
```

Add additional container images:
```bash
python generator.py --ocp-versions 4.14.1 --operators logging --additional-images registry.redhat.io/ubi8/ubi:latest,quay.io/my-org/my-app:v1.0.0
```

Create sample configuration:
```bash
python generator.py --create-sample-config
```

## Configuration File Format

```json
{
  "ocp_versions": ["4.14.1", "4.14.2", "4.14.3"],
  "ocp_channel": "stable-4.14",
  "operators": [
    "cluster-logging",
    "cluster-monitoring-operator", 
    "servicemeshoperator",
    "serverless-operator"
  ],
  "operator_catalog": "registry.redhat.io/redhat/redhat-operator-index:v4.14",
  "additional_images": [
    "registry.redhat.io/ubi8/ubi:latest"
  ],
  "helm_charts": [
    {
      "name": "prometheus",
      "repository": "https://prometheus-community.github.io/helm-charts",
      "version": "15.0.0"
    }
  ],
  "output_file": "imageset-config.yaml"
}
```

## Operator Name Mapping

The tool includes intelligent operator name mapping to convert common suggestions to actual package names:

| Suggestion | Actual Package Name |
|------------|-------------------|
| logging | cluster-logging |
| monitoring | cluster-monitoring-operator |
| service-mesh, istio | servicemeshoperator |
| serverless, knative | serverless-operator |
| pipelines, tekton | openshift-pipelines-operator-rh |
| gitops, argocd | openshift-gitops-operator |
| storage, ocs, ceph | odf-operator |

## Web API Endpoints

The Flask backend provides a REST API:

- `GET /api/health` - Health check
- `GET /api/operators/mappings` - Get operator mappings
- `POST /api/generate/preview` - Generate YAML preview
- `POST /api/generate/download` - Generate and download YAML
- `POST /api/config/load` - Load configuration from file
- `POST /api/config/save` - Save configuration to file
- `GET /api/config/sample` - Get sample configuration
- `POST /api/validate` - Validate configuration

## Example Output

The generated ImageSetConfiguration YAML will look like:

```yaml
apiVersion: mirror.openshift.io/v1alpha2
kind: ImageSetConfiguration
metadata:
  name: openshift-imageset
  labels:
    generated-by: imageset-generator
    generated-at: '2025-07-29T10:30:00.000000'
spec:
  archiveSize: 4
  mirror:
    platform:
      channels:
      - name: stable-4.14
        type: ocp
        minVersion: 4.14.1
        maxVersion: 4.14.2
      graph: true
    operators:
    - catalog: registry.redhat.io/redhat/redhat-operator-index:v4.14
      packages:
      - name: cluster-logging
      - name: cluster-monitoring-operator
    additionalImages:
    - name: registry.redhat.io/ubi8/ubi:latest
    helm: {}
```

## Using with oc-mirror

Once you have generated the ImageSetConfiguration file, you can use it with oc-mirror:

```bash
# Mirror to disk
oc-mirror --config imageset-config.yaml file://mirror-output

# Mirror to registry
oc-mirror --config imageset-config.yaml docker://your-registry.example.com:5000
```

## Development

### Project Structure
```
.
├── generator.py          # Core generator logic and CLI
├── gui.py               # Tkinter desktop GUI
├── app.py               # Flask web application backend
├── launcher.py          # Unified launcher script
├── frontend/            # React web frontend
│   ├── src/
│   │   ├── App.js
│   │   ├── components/
│   │   └── ...
│   └── package.json
├── requirements.txt     # Python dependencies
├── start-web.sh        # Web app startup script
├── start-dev.sh        # Development startup script
├── start-podman.sh     # Podman deployment script
├── start-podman-dev.sh # Podman development script
├── Containerfile       # Container build definition
└── README.md
```

### Running in Development Mode

For web interface development:
```bash
./start-dev.sh
```

This starts both Flask backend (port 5000) and React dev server (port 3000) with hot reload.

### Building for Production

```bash
cd frontend
npm run build
cd ..
python app.py
```

### Container Deployment

Build and run with Podman:
```bash
podman build -t imageset-generator .
podman run -d -p 5000:5000 --name imageset-generator imageset-generator
```

Or use the provided scripts:
```bash
./start-podman.sh          # Production
./start-podman-dev.sh      # Development
```

## Command Line Options

```
usage: generator.py [-h] [--ocp-versions OCP_VERSIONS] [--ocp-channel OCP_CHANNEL]
                   [--operators OPERATORS] [--operator-catalog OPERATOR_CATALOG]
                   [--additional-images ADDITIONAL_IMAGES] [--config CONFIG]
                   [--output OUTPUT] [--create-sample-config]

Generate OpenShift ImageSetConfiguration files

optional arguments:
  -h, --help            show this help message and exit
  --ocp-versions OCP_VERSIONS
                        Comma-separated list of OCP versions (e.g., '4.14.1,4.14.2')
  --ocp-channel OCP_CHANNEL
                        OCP channel name (default: stable-4.14)
  --operators OPERATORS
                        Comma-separated list of operator names/suggestions
  --operator-catalog OPERATOR_CATALOG
                        Operator catalog source
  --additional-images ADDITIONAL_IMAGES
                        Comma-separated list of additional container images
  --config CONFIG       Path to JSON configuration file
  --output OUTPUT       Output file name (default: imageset-config.yaml)
  --create-sample-config
                        Create a sample configuration file
```

## License

This project is open source and available under the MIT License.
