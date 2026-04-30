# Development Tools

Standalone utilities for maintaining the clarity-agent project. These are not part of the main CLI — they're developer-facing tools for specific maintenance tasks.

## Tools

| File | Purpose |
| ---- | ------- |
| `refresh-catalog.py` | Updates `catalogs/security-catalog.csv` with latest threat intelligence. Interactive AI conversation that searches the web and proposes changes for human approval. |
| `requirements.txt` | Python dependencies needed by the dev tools in this directory. |

## Usage

```bash
# Update the security threat catalog
python dev-tools/refresh-catalog.py
```

## See Also

- [README.md](../README.md) — Main project README and quickstart
- [CONTRIBUTING.md](../CONTRIBUTING.md) — Full developer guide
