<div align="center">

# ⚙️ Enron Scripts

**Utility scripts for the Enron Evaluation Environment.**

</div>

---

## Structure

| Path | Contents |
|:---|:---|
| [`eda/`](eda/) | EDA generation scripts |
| [`eda/generate_figures.py`](eda/generate_figures.py) | Static figure generation |
| [`eda/generate_interactive.py`](eda/generate_interactive.py) | Interactive chart generation |

## Usage

```bash
cd packages/Enron-Evaluation-Environment

# Generate all figures
python scripts/eda/generate_figures.py

# Generate interactive charts
python scripts/gen_interactive_charts.py
```

## Related Files

- `reports/` — Generated reports and figures
- `tests/` — Test suites
