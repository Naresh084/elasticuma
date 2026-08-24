# Paper chart map

## Gate-1 fixed expert-cache sweep

- Analytical question: how does explicit expert-cache capacity affect decode
  throughput, cache effectiveness, and unified-memory pressure on the measured
  M1 Max/Qwen workload?
- Takeaway: hit rate rises monotonically, while throughput and memory headroom
  deteriorate; the strongest paired throughput gap is repeatable but below the
  preregistered 15% threshold.
- Family and variant: ordered quantitative comparison; four aligned line/dot
  panels with uncertainty/benchmark in the throughput panel.
- Grain and sufficiency: six ordered cache sizes, five admitted repetitions per
  size, batch size one. A line is used only because cache size is an ordered
  numeric control; individual points remain visible.
- Fields: expert slots, cache MiB, decode token/s, expert hit rate, minimum free
  percentage, peak compressor growth GiB, repetition, 15% threshold, 25% safety
  guard.
- Palette: single-root blue for throughput; gold for hit rate; orange for free
  memory; olive for compressor; dark-neutral thresholds. Markers, labels, and
  line styles keep distinctions legible without color.
- Surface: reproducible static SVG and PNG for the Markdown/paper artifact.
- Source: admitted Gate-1 v4 JSON, SHA-256
  `094d9f73549c332046fbfeb5459d2338c12ae5eb9494f473319a6a97b5910ab8`.
- QA: inspect the exported PNG at native resolution and the SVG metadata; verify
  zero-based rate/pressure axes, exact 15% annotation, no clipped labels, and
  consistency with the generated summary CSV.
