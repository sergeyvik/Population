# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run simulation (interactive, opens plots)
uv run population simulate --men 50000 --women 50000 --years 50

# Run from config file (CLI flags override config values)
uv run population simulate --config configs/default.yaml

# Save output without showing
uv run population simulate --config configs/default.yaml --output save

# Validate a config file without running simulation
uv run population validate-config configs/default.yaml

# Run as module
uv run python -m population simulate --help
```

## Architecture

**Cohort-component demographic model**: population is tracked as two arrays of shape `(101,)` — one per sex, indexed by age 0–100.

Each simulation step (`model.step()`):
1. Apply age-specific mortality rates element-wise
2. Shift cohorts by 1 year (age everyone up)
3. Compute births from fertile women × `birth_rate`, split by sex ratio

Key modules:

- **`model.py`** — `PopulationModel`, `PopulationState`, `SimulationParams`. Core simulation loop. `model.history` is a list of `PopulationState` snapshots.
- **`cli.py`** — Typer CLI commands: `simulate` and `validate-config`. Config resolution order: CLI flag → YAML config → hardcoded default.
- **`mortality.py`** — `parse_mortality(spec)` returns `(male_array, female_array)`. Formats: `gompertz`, `gompertz:0.015`, `0.012` (flat), `config:file.yaml`.
- **`distributions.py`** — `parse_distribution(spec, men, women)` builds initial age arrays. Formats: `pyramid`, `pyramid:0.04`, `uniform:20-60`, `normal:35:12`, `single:30`, `config:file.yaml`.
- **`visualization.py`** — matplotlib pyramid plots; `save_pyramid`, `show_pyramid`, `save_animation`, `show_animation`.
- **`reporting.py`** — Rich terminal tables (`print_summary_table`, `print_state_info`).

## Key constraints

- `numpy<2.0` — pinned intentionally; do not upgrade.
- Python ≥ 3.12 required.
- Package managed with `uv` (not pip/poetry).
- Windows UTF-8 workaround is in `__main__.py`; do not remove it.

## Config format

YAML files in `configs/` follow the structure in `configs/default.yaml`. The `age_dist` and `mortality` fields accept the same spec strings as their CLI counterparts. Custom distributions and mortality tables can be loaded via `config:path/to/file.yaml`.
