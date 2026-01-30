# Agent Instructions

Instructions for AI assistants working on this project.

## Project Context

**Purpose:** Streamlit app for inventory distribution between stores (Russian retail chain).
**Stack:** Python 3.11+, Streamlit, Pandas, OpenPyXL.
**Deployment:** Streamlit Community Cloud (auto-deploy from `main`).

For module details see [ARCHITECTURE.md](ARCHITECTURE.md).

## Code Conventions

- **Chat:** German is fine for conversation
- **Code & Docs:** All code, comments, docstrings, and documentation must be in English
- **UI Text:** User-facing strings in Russian (Streamlit labels, messages, etc.)
- **Types:** Type hints for all functions
- **Tests:** Pytest in `tests/`, run before commit

## Common Tasks

### Run tests
```bash
pytest tests/ -v
```

### Test app locally
```bash
streamlit run app.py
```

### Import test
```bash
python3 -c "import app; print('OK')"
```

## Important Files

| File | When relevant |
|------|---------------|
| `core/config.py` | Column names, default priorities |
| `core/distributor.py` | Change distribution logic |
| `core/filters.py` | Add new filter options |
| `ui/preview.py` | Preview display |

## Known Quirks

1. **Header row:** Excel files have header in row 7, sub-header in row 8
2. **Session state:** Each tab needs unique `prefix` for widget keys
3. **Cyrillic columns:** Column names are in Russian (`Номенклатура`, `Характеристика`)

## Deployment

After push to `main`:
1. Streamlit Cloud pulls automatically
2. If issues: Use "Reboot app" in Streamlit Cloud dashboard
