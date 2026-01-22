# FLS Installation Guide

## Prerequisites

- Python 3.8 or higher
- `pip` for optional dependencies
- Internet access for API queries

## Installation Methods

### Method 1: Clone into Your Project

```bash
cd /path/to/your/research/project

# Clone FLS
git clone https://github.com/SproutSeeds/fls.git

# Create your config
cp fls/templates/config.template.json fls_config.json

# Edit config with your keywords
nano fls_config.json
```

### Method 2: Use the Init Script

```bash
# Download and run the init script
curl -O https://raw.githubusercontent.com/SproutSeeds/fls/main/scripts/fls-init.sh
chmod +x fls-init.sh

# Initialize FLS in your project
./fls-init.sh /path/to/your/project
```

The init script will:
1. Create the required directory structure
2. Copy scripts and templates
3. Generate a starter config
4. Initialize the state file

### Method 3: Copy Manually

1. Download or clone the FLS repository
2. Copy these to your project:
   - `scripts/literature_scan.py`
   - `scripts/orchestrate_summarization.py`
   - `templates/config.template.json` → `fls_config.json`
   - `templates/state.template.json` → `fls_state.json`

## Directory Structure

After installation, your project should have:

```
your-project/
├── fls_config.json          # Your configuration
├── fls_state.json           # Scan state (auto-managed)
├── LITERATURE_WORLD_MODEL.md  # Structured paper summaries
├── papers/                  # Downloaded PDFs
│   └── papers_manifest.json # Paper metadata
└── fls/                     # FLS scripts (or in PATH)
    └── scripts/
```

## Configuration

### Minimal Config

```json
{
  "primary_keywords": ["your", "research", "terms"],
  "secondary_keywords": ["related", "terms"],
  "arxiv_categories": ["math.CO"],
  "download_dir": "papers",
  "world_model_file": "LITERATURE_WORLD_MODEL.md"
}
```

### Full Config Options

See `templates/config.template.json` for all options with documentation.

## API Keys (Optional)

### Semantic Scholar

Increases rate limits from 100 to 5000 requests/day.

1. Get a free key at: https://www.semanticscholar.org/product/api
2. Set environment variable:
   ```bash
   export FLS_SEMANTIC_SCHOLAR_API_KEY="your-key-here"
   ```
3. Or add to your shell profile (`~/.bashrc`, `~/.zshrc`)
4. Or use `.env.local` (auto-loaded). Start from `.env.example`.

### arXiv

No API key needed. arXiv API is free and open.

### OEIS

No API key needed. OEIS is queried via simple HTTP.

### Unpaywall

Unpaywall requests must include your email as a query parameter. Set:

```bash
export FLS_UNPAYWALL_EMAIL="you@yourdomain.com"
```
Or put it in `.env.local` (auto-loaded).

## Verify Installation

```bash
# Interactive pipeline runner (recommended)
python3 fls/scripts/fls.py --config fls_config.json

# Test the scanner
python3 fls/scripts/literature_scan.py --config fls_config.json --help

# Run a test scan (won't download, just shows what would be found)
python3 fls/scripts/literature_scan.py --config fls_config.json

# Build/update local RAG index (offline)
python3 fls/scripts/rag_index.py --config fls_config.json

# Smoke test API connectivity (optional)
# Note: Unpaywall requires your real email (set FLS_UNPAYWALL_EMAIL or unpaywall_email in config)
python3 fls/scripts/smoke_test_apis.py
# (Optional) require Unpaywall to be configured:
# python3 fls/scripts/smoke_test_apis.py --require-unpaywall

# Smoke test local RAG (no network)
python3 fls/scripts/smoke_test_rag.py
```

## Optional Dependencies

For PDF text extraction (local RAG indexing + deep summarization):

```bash
pip install -r fls/requirements.txt
```

For scanned (image-only) PDFs, you may also want OCR tooling installed locally:

- macOS (Homebrew): `brew install tesseract poppler`
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr poppler-utils`

## Troubleshooting

### "No module named X"

FLS has no required dependencies. If you see this, check:
- Python version: `python3 --version` (need 3.8+)
- Running from correct directory

### "Permission denied"

```bash
chmod +x fls/scripts/*.py
chmod +x fls/scripts/*.sh
```

### "Config file not found"

Ensure you pass `--config` with the correct path:
```bash
python3 fls/scripts/literature_scan.py --config ./fls_config.json --delta
```

### Rate limiting (429 errors)

- Semantic Scholar: Get an API key (see above)
- arXiv: Increase `arxiv_delay_seconds` in config (default: 3)

## Next Steps

1. [Customize your config](docs/CUSTOMIZATION.md)
2. [Integrate with your AI assistant](docs/AGENT_INTEGRATION.md)
3. [Run your first scan](USAGE.md)
