# Inventory Distribution App

A Streamlit web app for distributing inventory between retail stores.

## Features

- **Stock → Stores**: Distributes items from warehouse to stores with 0 inventory
- **Balance Inventory**: Balances inventory between stores
- **Sales-based Priority**: Stores with more sales get higher priority
- **Flexible Filters**: Filter by article type, collection, additional name

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run app
streamlit run app.py
```

## Deployment

Hosted on **Streamlit Community Cloud**:
- Auto-deploys on push to `main`
- Config in `.streamlit/config.toml`

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for code structure details.

## Development

```bash
# Run tests
pytest tests/ -v

# Start app locally
streamlit run app.py
```

## Input Format

Excel files with:
- Header in row 7 (auto-detected)
- Columns: `Номенклатура`, `Характеристика`, `Сток`, store columns
