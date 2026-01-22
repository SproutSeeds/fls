# API Keys Configuration

FLS works without any API keys, but adding them improves rate limits and access.

## Semantic Scholar API Key

**Why:** Increases rate limit from 100 to 5,000 requests per day.

**How to get:**
1. Go to https://www.semanticscholar.org/product/api
2. Click "Get API Key"
3. Sign up or log in
4. Copy your API key

**How to set:**

```bash
# Option 1: Export in terminal
export FLS_SEMANTIC_SCHOLAR_API_KEY="your-key-here"

# Option 2: Add to shell profile (~/.bashrc, ~/.zshrc)
echo 'export FLS_SEMANTIC_SCHOLAR_API_KEY="your-key-here"' >> ~/.zshrc
source ~/.zshrc

# Option 3: Create a local env file (recommended)
# FLS scripts auto-load `.env.local` (then `.env`) from your working directory.
cp .env.example .env.local
# Edit `.env.local` and set:
# FLS_SEMANTIC_SCHOLAR_API_KEY=your-key-here
```

## arXiv API

**No key needed.** arXiv API is free and open.

Default rate limit: 1 request per 3 seconds (FLS handles this automatically).

## OEIS

**No key needed.** OEIS is queried via simple HTTP.

## Unpaywall (Email Required)

Unpaywall does not use API keys, but **requests must include your email** as a query parameter.

FLS supports this via:

```bash
# Option 1: Export in terminal
export FLS_UNPAYWALL_EMAIL="you@yourdomain.com"
```

Or put it in `.env.local` (recommended) or set `unpaywall_email` in your `fls_config.json`.

See `docs/UNPAYWALL.md` for endpoint details and usage notes.

## Troubleshooting

### HTTP 429 (Too Many Requests)

If you see this error:
- **Semantic Scholar:** Get an API key (see above)
- **arXiv:** Increase `arxiv_delay_seconds` in config (default: 3)
- **OEIS:** Increase `oeis_delay_seconds` in config (default: 1.5)

### API Key Not Working

1. Check the key is set correctly:
   ```bash
   echo $FLS_SEMANTIC_SCHOLAR_API_KEY
   ```

2. Verify it's exported (not just set):
   ```bash
   export FLS_SEMANTIC_SCHOLAR_API_KEY="your-key"
   ```

3. Restart your terminal or source your profile:
   ```bash
   source ~/.zshrc  # or ~/.bashrc
   ```
