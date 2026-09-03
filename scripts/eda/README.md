<div align="center">

# 📁 Enron EDA Scripts

**Exploratory Data Analysis scripts for the Enron Email Dataset.**

</div>

---

## Scripts

| Script | Description |
|:---|:---|
| `generate_figures.py` | Static matplotlib/seaborn charts |
| `generate_interactive.py` | Interactive Plotly HTML charts |

## Usage

```bash
cd packages/Enron-Evaluation-Environment
python scripts/eda/generate_figures.py
python scripts/eda/generate_interactive.py
```

## Output

Generated charts are saved to:
- `reports/eda/figures/` — Static PNGs
- `reports/eda/figures_interactive/` — Interactive HTMLs

## Related Files

- `reports/eda/` — Generated reports
- `scripts/gen_interactive_charts.py` — Alternative interactive generator
