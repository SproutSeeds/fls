#!/bin/bash
#
# FLS — Frontier Literature Scanner
# Project Initialization Script
#
# Usage: ./fls-init.sh /path/to/your/project [--example sunflower-conjecture]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLS_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "FLS — Frontier Literature Scanner Initialization"
    echo ""
    echo "Usage: $0 <project-path> [options]"
    echo ""
    echo "Options:"
    echo "  --example <name>    Use example config (e.g., sunflower-conjecture)"
    echo "  --help              Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/my-project"
    echo "  $0 . --example sunflower-conjecture"
}

if [[ $# -lt 1 ]] || [[ "$1" == "--help" ]]; then
    usage
    exit 0
fi

PROJECT_PATH="$1"
EXAMPLE=""

# Parse options
shift
while [[ $# -gt 0 ]]; do
    case $1 in
        --example)
            EXAMPLE="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Resolve project path
PROJECT_PATH="$(cd "$PROJECT_PATH" 2>/dev/null && pwd)" || {
    echo -e "${RED}Error: Invalid project path${NC}"
    exit 1
}

echo -e "${GREEN}FLS Initialization${NC}"
echo "===================="
echo "Project: $PROJECT_PATH"
echo ""

# Create directory structure
echo -e "${YELLOW}Creating directory structure...${NC}"
mkdir -p "$PROJECT_PATH/fls/scripts"
mkdir -p "$PROJECT_PATH/fls/scripts/lib"
mkdir -p "$PROJECT_PATH/fls/templates"
mkdir -p "$PROJECT_PATH/papers"

# Copy scripts
echo -e "${YELLOW}Copying scripts...${NC}"
cp "$FLS_ROOT/scripts/literature_scan.py" "$PROJECT_PATH/fls/scripts/"
cp "$FLS_ROOT/scripts/orchestrate_summarization.py" "$PROJECT_PATH/fls/scripts/"
cp "$FLS_ROOT/scripts/unpaywall_query.py" "$PROJECT_PATH/fls/scripts/"
cp "$FLS_ROOT/scripts/fls.py" "$PROJECT_PATH/fls/scripts/"
cp "$FLS_ROOT/scripts/rag_index.py" "$PROJECT_PATH/fls/scripts/"
cp "$FLS_ROOT/scripts/rag_query.py" "$PROJECT_PATH/fls/scripts/"
cp "$FLS_ROOT/scripts/smoke_test_apis.py" "$PROJECT_PATH/fls/scripts/"
cp "$FLS_ROOT/scripts/smoke_test_rag.py" "$PROJECT_PATH/fls/scripts/"
cp "$FLS_ROOT/scripts/lib/"*.py "$PROJECT_PATH/fls/scripts/lib/"
cp "$FLS_ROOT/requirements.txt" "$PROJECT_PATH/fls/requirements.txt"
cp "$FLS_ROOT/templates/"*.md "$PROJECT_PATH/fls/templates/" 2>/dev/null || true
cp "$FLS_ROOT/templates/"*.json "$PROJECT_PATH/fls/templates/" 2>/dev/null || true

# Make scripts executable
chmod +x "$PROJECT_PATH/fls/scripts/"*.py

# Copy or create config
if [[ -n "$EXAMPLE" ]]; then
    EXAMPLE_PATH="$FLS_ROOT/examples/$EXAMPLE/config.json"
    if [[ -f "$EXAMPLE_PATH" ]]; then
        echo -e "${YELLOW}Using example config: $EXAMPLE${NC}"
        cp "$EXAMPLE_PATH" "$PROJECT_PATH/fls_config.json"
    else
        echo -e "${RED}Example not found: $EXAMPLE${NC}"
        echo "Available examples:"
        ls "$FLS_ROOT/examples/"
        exit 1
    fi
else
    echo -e "${YELLOW}Creating config from template...${NC}"
    cp "$FLS_ROOT/templates/config.template.json" "$PROJECT_PATH/fls_config.json"
fi

# Create state file
echo -e "${YELLOW}Initializing state file...${NC}"
cp "$FLS_ROOT/templates/state.template.json" "$PROJECT_PATH/fls_state.json"

# Create world model
echo -e "${YELLOW}Creating world model template...${NC}"
cp "$FLS_ROOT/templates/WORLD_MODEL.template.md" "$PROJECT_PATH/LITERATURE_WORLD_MODEL.md"

# Copy env example (optional)
if [[ -f "$FLS_ROOT/.env.example" ]] && [[ ! -f "$PROJECT_PATH/.env.example" ]]; then
    echo -e "${YELLOW}Copying .env.example...${NC}"
    cp "$FLS_ROOT/.env.example" "$PROJECT_PATH/.env.example"
fi

# Ensure local env files are git-ignored
if [[ -f "$PROJECT_PATH/.gitignore" ]]; then
    if ! grep -qE '^[[:space:]]*\\.env\\.local[[:space:]]*$' "$PROJECT_PATH/.gitignore"; then
        echo -e "${YELLOW}Updating .gitignore to ignore .env.local...${NC}"
        {
            echo ""
            echo "# Local env files (FLS)"
            echo ".env"
            echo ".env.local"
            echo ".fls_last_config"
        } >> "$PROJECT_PATH/.gitignore"
    fi
else
    echo -e "${YELLOW}Note:${NC} add .env.local and .fls_last_config to your project's .gitignore to avoid committing them."
fi

# Summary
echo ""
echo -e "${GREEN}FLS initialized successfully!${NC}"
echo ""
echo "Created files:"
echo "  fls_config.json           - Configuration (edit this!)"
echo "  fls_state.json            - Scan state"
echo "  LITERATURE_WORLD_MODEL.md - Paper summaries"
echo "  .env.example              - Example env vars (copy to .env.local)"
echo "  fls/requirements.txt      - Optional deps for PDF extraction (RAG)"
echo "  fls/scripts/              - FLS scripts"
echo "  papers/                   - PDF download directory"
echo ""
echo "Next steps:"
echo "  1. Edit fls_config.json with your research keywords"
echo "  1b. (Optional) Install PDF extraction deps: pip install -r fls/requirements.txt"
echo "  2. Run (recommended): python3 fls/scripts/fls.py --config fls_config.json"
echo "     Or step-by-step:  python3 fls/scripts/literature_scan.py --config fls_config.json --delta"
echo "  3. Check LITERATURE_WORLD_MODEL.md for results"
echo "  4. (Optional) Build local RAG index: python3 fls/scripts/rag_index.py --config fls_config.json"
echo ""
echo "For agent integration, start from:"
echo "  fls/templates/AGENT.template.md (model-agnostic)"
echo "  fls/templates/CLAUDE.template.md (Claude-specific)"
