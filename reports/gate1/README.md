# Gate-1 technical report

`report.html` is the self-contained, read-only technical report for the complete
Gate-1 v4 snapshot. `artifact.json` is its canonical validated source, and
`evidence/` contains the reviewed public CSV rows used by its charts and table.

The Data Analytics portable builder reported:

- validation: passed;
- packaging: passed;
- verification: structural only;
- blocks: 16;
- charts: 2;
- metric cards: 4;
- tables: 1.

Enhanced browser verification was unavailable because no compatible Chromium
headless-shell binary was installed. The builder performed exact payload and
semantic-fallback structural verification and did not download a browser. The
tracked static paper figure was separately rendered and visually inspected.

Regenerate the canonical input and public tables with:

```bash
uv run python scripts/build_gate1_report.py \
  --admitted artifacts/admitted/gate1-m1max-qwen36-q4-v4.json \
  --analysis artifacts/figures/gate1-m1max-qwen36-q4-v4-analysis.json \
  --output-dir reports/gate1
```
