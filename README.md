# morph-replay-runner

**morph-replay-runner** is a command-line interface (CLI) tool designed to execute TRACE-REPLAY-KIT bundles with branch-N parallelism on Morph Cloud. This tool streamlines the process of running replay tasks, ensuring efficient and scalable execution with comprehensive evidence collection and CERT-V1 compliance.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Usage](#usage)
4. [Configuration](#configuration)
5. [Error Handling](#error-handling)
6. [Project Structure](#project-structure)
7. [Examples](#examples)
8. [Docker Support](#docker-support)
9. [CI/CD Pipeline](#cicd-pipeline)
10. [Contributing](#contributing)
11. [License](#license)

## Installation

### Prerequisites

- Python 3.9 or later
- Morph Cloud API key
- Access to Morph Cloud snapshots

### Install from Source

```bash
# Clone the repository
git clone https://github.com/SentinelOps-CI/morph-replay-runner.git
cd morph-replay-runner

# Install in development mode
pip install -e .
```

### Install Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Or install with development tools
pip install -e ".[dev]"
```

## Quick Start

```bash
# Basic usage
replay-runner \
  --snapshot morphvm-minimal \
  --bundles "./replays/*.zip" \
  --parallel 4 \
  --emit-cert \
  --out ./evidence

# With HTTP callbacks
replay-runner \
  --snapshot morphvm-minimal \
  --bundles "./examples/*.zip" \
  --parallel 2 \
  --http-callback \
  --http-port 8080 \
  --http-auth api_key

# Asynchronous mode
replay-runner \
  --snapshot morphvm-minimal \
  --bundles "./replays/*.zip" \
  --parallel 8 \
  --async \
  --timeout 1200
```

## Usage

### Command Line Options

```bash
replay-runner --help
```

**Required Options:**
- `--snapshot`: Base snapshot ID or digest containing sidecar + replay tools
- `--bundles`: Glob pattern for replay bundles (e.g., `./replays/*.zip`)

**Optional Options:**
- `-p, --parallel`: Number of parallel instances (default: 4)
- `-t, --timeout`: Execution timeout in seconds (default: 600)
- `--emit-cert/--no-emit-cert`: Emit CERT-V1 JSON certificates (default: True)
- `-o, --out`: Output directory for evidence collection (default: `./evidence`)
- `--async`: Use asynchronous execution mode
- `--http-callback`: Enable HTTP callback service for demos
- `--http-port`: Port for HTTP callback service (default: 8080)
- `--http-auth`: HTTP callback authentication mode (`none` or `api_key`)

### Basic Workflow

1. **Prepare Replay Bundles**: Create TRACE-REPLAY-KIT compliant zip files
2. **Set Environment**: Configure your Morph Cloud API key
3. **Execute**: Run the tool with appropriate parameters
4. **Collect Evidence**: Review generated certificates, logs, and reports

## Configuration

### Environment Variables

```bash
# Set your Morph Cloud API key
export MORPH_API_KEY="your_api_key_here"
```

### Configuration File

The tool automatically detects and uses the `MORPH_API_KEY` environment variable. For advanced configuration, you can modify the `pyproject.toml` file.

## Error Handling

The tool utilizes standard Python exceptions such as `ValueError` and `Exception` to handle errors gracefully. Common error scenarios include:

- **API Key Missing**: Ensure `MORPH_API_KEY` is set
- **Snapshot Not Found**: Verify snapshot ID exists in Morph Cloud
- **Bundle Format Issues**: Ensure bundles are valid TRACE-REPLAY-KIT format
- **Network Issues**: Check connectivity to Morph Cloud

## Project Structure

```
morph-replay-runner/
├── runner/                 # Main runner package
│   ├── __init__.py        # Package initialization
│   ├── main.py            # CLI entry point
│   ├── core.py            # Core execution logic
│   └── models.py          # Data models
├── schemas/                # JSON schemas
│   ├── cert_v1.json       # CERT-V1 schema
│   ├── trace_replay_kit.json # TRACE-REPLAY-KIT schema
│   └── replay_runner.json # Internal schemas
├── examples/               # Demo replay bundles
│   ├── demo-http.json     # HTTP demo
│   ├── demo-tcp.json      # TCP demo
│   └── demo-file.json     # File operations demo
├── docker/                 # Docker support
│   ├── Dockerfile         # Container image
│   └── docker-compose.yml # Multi-service setup
├── .github/workflows/      # CI/CD workflows
│   └── replay.yml         # Matrix testing workflow
├── pyproject.toml         # Project configuration
├── requirements.txt        # Dependencies
└── README.md              # This file
```

## Examples

### Demo Bundles

The project includes three example replay bundles:

1. **HTTP Demo** (`examples/demo-http.json`): HTTP GET request to httpbin.org
2. **TCP Demo** (`examples/demo-tcp.json`): TCP connection to localhost:8080
3. **File Demo** (`examples/demo-file.json`): File operations in /tmp

### Creating Custom Bundles

```json
{
  "version": "2.1.0",
  "manifest": {
    "bundle_id": "my-custom-replay",
    "created_at": "2025-01-01T00:00:00Z",
    "description": "Custom replay description",
    "tags": ["custom", "demo"],
    "author": "Your Name"
  },
  "replay_data": {
    "type": "http",
    "payload": {
      "method": "GET",
      "url": "https://api.example.com/endpoint"
    }
  }
}
```

## Docker Support

### Build and Run

```bash
# Build the Docker image
docker build -f docker/Dockerfile -t morph-replay-runner .

# Run with Docker
docker run -e MORPH_API_KEY="your_key" morph-replay-runner --help
```

### Docker Compose

```bash
# Start services
docker-compose -f docker/docker-compose.yml up

# Run with mounted volumes
docker-compose -f docker/docker-compose.yml run morph-replay-runner \
  --snapshot morphvm-minimal \
  --bundles "/app/replays/*.zip"
```

## CI/CD Pipeline

The project includes a comprehensive GitHub Actions workflow that:

- **Matrix Testing**: Tests across Python versions (3.9, 3.10, 3.11)
- **Bundle Validation**: Tests different bundle types (HTTP, TCP, File)
- **Parallel Execution**: Tests various parallel instance counts
- **Evidence Collection**: Validates generated certificates and reports
- **Artifact Publishing**: Uploads evidence packs for review

### Workflow Triggers

- **Push**: Automatically runs on pushes to `main` and `develop` branches
- **Pull Request**: Runs on all PRs for quality assurance
- **Manual Dispatch**: Can be triggered manually with custom parameters

## Testing

### Local Testing

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code quality checks
black .
isort .
ruff check .
mypy .
```

### CI Testing

The CI pipeline automatically:
- Creates demo bundles
- Executes replay runner
- Validates evidence collection
- Generates summary reports

## Output Structure

```
evidence/
├── certs/                  # CERT-V1 certificates
│   ├── cert_0.json        # Bundle 0 certificate
│   ├── cert_1.json        # Bundle 1 certificate
│   └── ...
├── logs/                   # Execution logs
│   ├── log_0.txt          # Bundle 0 log
│   ├── log_1.txt          # Bundle 1 log
│   └── ...
└── reports/                # Summary reports
    └── index.json         # Execution summary
```

## Contributing

We welcome contributions to **morph-replay-runner**! To contribute:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add tests for new functionality
- Update documentation as needed
- Ensure all CI checks pass

### Code Quality Tools

- **Black**: Code formatting
- **Isort**: Import sorting
- **Ruff**: Linting and formatting
- **MyPy**: Type checking

## License

**morph-replay-runner** is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for more details.
