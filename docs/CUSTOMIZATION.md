# Customizing FLS for Your Research Domain

FLS is designed to work with any research domain. This guide explains how to tune it for your specific needs.

## Keyword Strategy

### Primary Keywords

These are **required** - a paper must match at least `min_primary_hits` of these.

**Good primary keywords:**
- Specific technical terms unique to your problem
- Problem names (e.g., "sunflower conjecture", "P vs NP")
- Key mathematical objects (e.g., "cap set", "Ramsey number")

**Bad primary keywords:**
- Generic terms ("algorithm", "proof", "bound")
- Common words that appear in many papers

**Example for Sunflower Conjecture:**
```json
{
  "primary_keywords": [
    "sunflower",
    "delta-system",
    "Δ-system",
    "sunflower-free"
  ],
  "min_primary_hits": 1
}
```

### Secondary Keywords

These improve relevance scoring but aren't required.

**Good secondary keywords:**
- Related concepts
- Author names known for the area
- Specific techniques

**Example:**
```json
{
  "secondary_keywords": [
    "Erdos-Rado",
    "spread lemma",
    "polynomial method",
    "cap set"
  ]
}
```

## arXiv Categories

Choose categories relevant to your research:

| Category | Area |
|----------|------|
| `math.CO` | Combinatorics |
| `math.NT` | Number Theory |
| `math.PR` | Probability |
| `math.AG` | Algebraic Geometry |
| `cs.DM` | Discrete Mathematics |
| `cs.CC` | Computational Complexity |
| `cs.DS` | Data Structures & Algorithms |
| `physics.math-ph` | Mathematical Physics |

**Example:**
```json
{
  "arxiv_categories": ["math.CO", "math.NT", "cs.CC"]
}
```

## OEIS Integration

If your research involves integer sequences, enable OEIS:

```json
{
  "sources": {
    "arxiv": true,
    "semantic_scholar": true,
    "oeis": true
  },
  "oeis_sequences": [
    [1, 3, 5, 8, 12, 19],
    [2, 4, 6, 9, 13, 20]
  ]
}
```

FLS will search OEIS for these sequences and alert you if they're already catalogued.

## Research Context

The `research_context` field is injected into AI prompts for better relevance assessment:

```json
{
  "research_context": "We are studying the weak sunflower conjecture, focusing on exact values of m(n,3) for small n and whether growth is polynomial or exponential. We're particularly interested in coordinate-local methods and the gap between empirical growth (~1.55^n) and the Naslund-Sawin bound (~1.89^n)."
}
```

**Tips:**
- Be specific about what you care about
- Mention key quantities/values
- Note techniques you're using
- Highlight what would be most useful to find

## Scan Frequency

Adjust based on how active your field is:

| Field Activity | Suggested `freshness_hours` |
|----------------|----------------------------|
| Hot topic (many papers/week) | 6 |
| Active area | 12-24 |
| Slower field | 48-168 |

## World Model Fields

The auto-generated world model entries include:

- **Summary:** Auto-extracted from title
- **Method:** Detected from abstract keywords
- **Data:** Whether explicit values are mentioned
- **Gap:** Placeholder for what's missing
- **Actionable:** Suggested next step

To customize detection, you can modify `generate_world_model_entry()` in `literature_scan.py`.

## Example Configurations

### Theoretical Computer Science

```json
{
  "primary_keywords": ["P vs NP", "circuit complexity", "communication complexity"],
  "arxiv_categories": ["cs.CC", "cs.DS"],
  "research_context": "Lower bounds for Boolean circuits and communication protocols."
}
```

### Number Theory

```json
{
  "primary_keywords": ["Riemann hypothesis", "prime gaps", "L-functions"],
  "arxiv_categories": ["math.NT", "math.AG"],
  "research_context": "Analytic number theory and the distribution of primes."
}
```

### Combinatorics

```json
{
  "primary_keywords": ["Ramsey", "Turán", "extremal graph"],
  "arxiv_categories": ["math.CO"],
  "research_context": "Extremal combinatorics and Ramsey theory."
}
```
