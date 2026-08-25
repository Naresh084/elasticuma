# LaTeX source

`main.tex` is the publication-quality author-preprint source for ElasticUMA.
It uses a compact single-column research layout so figures, tables, algorithms,
and long citations remain readable without the large gaps produced by the old
Word section-break layout.

Build with Tectonic:

```bash
tectonic main.tex --outdir build --keep-logs --keep-intermediates
```

The final PDF is copied to `../ElasticUMA-paper.pdf` only after page-by-page
rendering and layout verification. Venue submission may require adapting the
same content to an official ACM, IEEE, or USENIX template.
