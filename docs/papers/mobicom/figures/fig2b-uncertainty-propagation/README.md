# Figure 2(b): uncertainty propagation

Source: [manuscript §4.4](../../MobiCom论文初稿_结果假设版.md), read on 2026-09-08. This figure describes the proposed computation; it does not assert experimental validation.

- `fig2b-uncertainty-propagation.drawio`: native editable shapes, separate text labels, and vector block arrows.
- `fig2b-uncertainty-propagation.svg`: text-preserving vector artwork, using Times New Roman with Times/serif fallbacks.
- `fig2b-uncertainty-propagation-preview.png`: preview only.
- `fig2b-uncertainty-propagation.mxgraph.xml`: graph model for draw.io MCP.
- `build_figure.py`: shared geometry and content source; run with Python 3 from any directory to regenerate the draw.io and SVG files.

The 1/K loss average depicts the manuscript's equal-weight accepted Monte Carlo samples. Each sample is an alternative body position at one time, shared across that time's subcarriers/channels. Each position is evaluated separately, with visible paths recomputed. All positions share theta and are compared against the same training CSI. The loop updates theta only, not the visual geometry distribution. Held-out prediction freezes theta. The caption and all annotations remain separately editable.

The inline figure caption may be removed when the manuscript supplies its own caption. Use the SVG at full two-column width; this is a detailed methodology panel.
