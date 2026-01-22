# Sunflower Conjecture Example

This is a complete working example of FLS configured for Erdős Problem #857 (the Weak Sunflower Conjecture).

## The Problem

**m(n, k)** = minimum m such that ANY m subsets of {1,...,n} contain a k-sunflower

A k-sunflower is a collection of k sets where every pair has the same intersection.

## Configuration Highlights

- **Primary keywords:** sunflower, delta-system, Δ-system
- **arXiv categories:** math.CO, math.PR, cs.DM, cs.CC
- **OEIS sequences:** Known M(n,3) and m(n,3) values
- **Freshness:** 6 hours (active research area)

## Usage

```bash
# From this directory:
cd examples/sunflower-conjecture

# Run a full scan (novelty report)
python3 ../../scripts/literature_scan.py --config config.json

# Run delta scan (download new papers)
python3 ../../scripts/literature_scan.py --config config.json --delta

# Check status
python3 ../../scripts/orchestrate_summarization.py --config config.json status
```

## Key Papers to Watch

- **Naslund-Sawin (2016)** - Current best upper bound (~1.89^n)
- **ALWZ (2019)** - Improved sunflower lemma bounds
- **Fukuyama papers** - Claims improved bounds (need verification)
- **Any paper with m(n,3) or M(n,3)** - Direct competition

## Research Context

This configuration is designed for a project that:
- Computes exact values of m(n,3) for small n
- Investigates whether growth is polynomial or exponential
- Exploits the LOCAL nature of the sunflower constraint
- Aims to improve on the Naslund-Sawin bound

## Adapting for Your Research

To adapt this for a different combinatorics problem:

1. Replace keywords with your problem's terminology
2. Adjust OEIS sequences to your known values
3. Update research_context with your focus
4. Tune freshness_hours based on field activity
