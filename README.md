# DefectDojo CLI Uploader

A powerful command-line interface for importing and reimporting security scan results into DefectDojo. Features both interactive wizard mode and direct command execution with intelligent scan type autocomplete.

## Features

- 🚀 **Interactive Wizard**: Step-by-step guided import process
- ⚡ **Direct Commands**: Quick import/reimport with command-line arguments
- 🎯 **Smart Autocomplete**: Intelligent scan type selection with fast Enter key support
- 🔍 **Scan Type Validation**: Validates scan types against DefectDojo's API schema
- 📊 **Import Summary**: Displays results with direct links to view scans
- 🔄 **Multiple Sources**: Load scan types from server, local file, or fallback list
- 🛡️ **Flexible Auth**: Token-based or username/password authentication

## Installation

### From Source
```bash
# Clone the repository
git clone <repository-url>
cd DefecDojoCLI

# Install in development mode
pip install -e .

# Or using uv (recommended)
uv venv && uv pip install -e .
```

### Using pip (when published to PyPI)
```bash
pip install defectdojo-uploader
```

**Note:** This package is not yet published to PyPI. For now, install from source using the method above.

## Quick Start

### 1. Set Environment Variables
```bash
export DOJO_URL="https://your-defectdojo-instance.com"
export DOJO_TOKEN="your-api-token"
# Or use username/password
export DOJO_USERNAME="your-username"
export DOJO_PASSWORD="your-password"
```

### 2. Interactive Mode (Recommended for first-time users)
```bash
dd-upload interactive
```

### 3. Direct Import
```bash
dd-upload direct --file scan-results.json --scan-type "ZAP Scan" --engagement-id 123
```

## Usage

### Interactive Mode

The interactive wizard guides you through the entire process:

```bash
dd-upload interactive
```

**Features:**
- Product selection with search
- Engagement creation/selection
- File path selection
- Smart scan type autocomplete
- Reimport or new import options

**Autocomplete Tips:**
- Type partial text (e.g., "semgr") and press Enter to auto-select "Semgrep JSON Report"
- Use Tab to cycle through multiple matches
- Dropdown always visible for clear feedback

### Direct Mode

For automation and scripting:

```bash
# Import to existing engagement
dd-upload direct \
  --file scan-results.json \
  --scan-type "ZAP Scan" \
  --engagement-id 123

# Import with product/engagement names (auto-creates if needed)
dd-upload direct \
  --file scan-results.json \
  --scan-type "Trivy Scan" \
  --product "My Product" \
  --engagement "Release 1.0" \
  --auto-create-context

# Reimport into existing test
dd-upload direct \
  --file updated-scan.json \
  --scan-type "Dependency Check Scan" \
  --test-id 456
```

### Command Options

#### Global Options
- `--url`: DefectDojo base URL (default: `DOJO_URL` env var)
- `--token`: API token (default: `DOJO_TOKEN` env var)
- `--username`: Username (default: `DOJO_USERNAME` env var)
- `--password`: Password (default: `DOJO_PASSWORD` env var)

#### Direct Mode Options
- `--file, -f`: Path to scan file (required)
- `--scan-type`: Scanner type (required)
- `--engagement-id`: Target engagement ID
- `--product`: Product name (used with `--engagement`)
- `--engagement`: Engagement name (used with `--product`)
- `--test-id`: Reimport into existing test
- `--min-severity`: Minimum severity filter (default: "Info")
- `--active/--no-active`: Set finding active status
- `--verified/--no-verified`: Set finding verified status
- `--auto-create-context`: Auto-create product/engagement
- `--api-spec`: Path to local OpenAPI JSON file
- `--scan-types-source`: Source for scan types (auto|server|file)
- `--validate-scan-type/--no-validate-scan-type`: Validate scan type

## Scan Type Sources

The tool can load scan types from multiple sources:

### 1. Server (Default)
Fetches scan types from your DefectDojo instance's OpenAPI schema:
- `/api/v2/oa3/openapi.json`
- `/api/v2/oa3/swagger.json`
- `/api/v2/schema/?format=openapi`

### 2. Local File
Use a local OpenAPI JSON file:
```bash
dd-upload direct --api-spec /path/to/openapi.json --scan-types-source file
```

### 3. Fallback List
If server/file sources fail, uses built-in common scan types:
- ZAP Scan
- Trivy Scan
- Checkov Scan
- Dependency Check Scan
- Burp Scan
- Snyk Scan
- SonarQube Scan
- Anchore Grype

## Examples

### Import ZAP Scan Results
```bash
dd-upload direct \
  --file zap-report.json \
  --scan-type "ZAP Scan" \
  --engagement-id 123 \
  --min-severity "Medium"
```

### Import Trivy Results with Auto-Creation
```bash
dd-upload direct \
  --file trivy-results.json \
  --scan-type "Trivy Scan" \
  --product "My Application" \
  --engagement "Security Scan v1.2" \
  --auto-create-context \
  --verified
```

### Reimport Updated Scan
```bash
dd-upload direct \
  --file updated-scan.json \
  --scan-type "Dependency Check Scan" \
  --test-id 456 \
  --active
```

### Interactive Mode with Custom API Spec
```bash
dd-upload interactive \
  --api-spec /path/to/custom-openapi.json \
  --scan-types-source file
```

## Output

### Import Summary
After successful import, you'll see a summary table:
```
┌─────────────────────────────────────────────────────────────┐
│                    DefectDojo Import Summary                │
├─────────────────────────────────────────────────────────────┤
│ test                    │ {'id': 123, 'title': 'ZAP Scan'} │
│ engagement              │ 456                               │
│ scan_type               │ ZAP Scan                          │
│ Scan URL                │ https://dojo.example.com/test/123│
└─────────────────────────────────────────────────────────────┘
```

The **Scan URL** provides a direct link to view the scan results in your browser.

## Configuration

### Environment Variables
```bash
# Required
export DOJO_URL="https://your-defectdojo-instance.com"

# Authentication (choose one)
export DOJO_TOKEN="your-api-token"
# OR
export DOJO_USERNAME="your-username"
export DOJO_PASSWORD="your-password"

# Optional
export DOJO_API_SPEC="/path/to/openapi.json"
```

### API Token Authentication (Recommended)
1. Log into your DefectDojo instance
2. Go to User Settings → API Key
3. Generate a new API key
4. Set `DOJO_TOKEN` environment variable

## Troubleshooting

### Common Issues

**"Invalid --scan-type" error:**
- Check available scan types: `dd-upload interactive --scan-types-source server`
- Use `--no-validate-scan-type` to bypass validation

**Authentication errors:**
- Verify your API token or username/password
- Check that your DefectDojo instance is accessible

**File not found:**
- Ensure the scan file path is correct and readable
- Use absolute paths if needed

**No scan types found:**
- Check your DefectDojo instance's API endpoints
- Try using `--scan-types-source file` with a local OpenAPI spec

### Debug Mode
For troubleshooting, you can see detailed output by setting:
```bash
export PYTHONPATH=.
python -m ddcli.cli interactive
```

## Development

### Project Structure
```
DefecDojoCLI/
├── ddcli/
│   ├── __init__.py
│   ├── cli.py          # Main CLI interface
│   └── api.py          # DefectDojo API client
├── pyproject.toml      # Project configuration
└── README.md
```

### Running Tests
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting section above
- Review DefectDojo documentation for scan format requirements

