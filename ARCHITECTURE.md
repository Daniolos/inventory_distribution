# Architecture

## Overview

```
app.py                    # Entry Point (341 LoC)
core/                     # Business Logic (UI-agnostic)
ui/                       # Streamlit UI Components
tests/                    # Pytest Tests
```

## Module Separation

| Directory | Streamlit-dependent | Purpose |
|-----------|---------------------|---------|
| `core/` | ❌ No | Business logic, CLI-capable |
| `ui/` | ✅ Yes | Streamlit components |
| `app.py` | ✅ Yes | Entry point, routing |

## Core Modules

### `core/distributor.py`
**StockDistributor** - Distributes warehouse → stores
- `preview(df, source, header_row)` → List[TransferPreview]
- `execute(df, source, header_row)` → List[TransferResult]
- `generate_updated_inventory(file, df, source, header_row)` → UpdatedInventoryResult

### `core/balancer.py`
**InventoryBalancer** - Balances inventory between stores
- `preview(df, header_row)` → List[TransferPreview]
- `execute(df, header_row)` → List[TransferResult]

**Balancing Logic:**
- Excess (> threshold) goes directly to Stock
- Exception: Store pairs (125004↔125005, 125008↔129877) can balance between each other first
- If partner has 0 inventory: 1 item to partner, rest to Stock
- If partner has inventory: all to Stock

### `core/config.py`
- `DEFAULT_STORE_PRIORITY` - Default store order
- `DEFAULT_EXCLUDED_STORES` - Default excluded stores
- `STORE_BALANCE_PAIRS` - Store pairs that can balance between each other

### `core/file_loader.py`
- `find_header_row(file)` - Auto-detects header row
- `load_excel_with_header(file)` - Loads with header detection

### `core/filters.py`
- `extract_article_name(nomenclature)` - Extracts article name
- `apply_all_filters(df, ...)` - Filters DataFrame

### `core/models.py`
Dataclasses: `Transfer`, `TransferPreview`, `TransferResult`, `DistributionConfig`, `UpdatedInventoryResult`

**DistributionConfig** fields:
- `store_priority` - Store priority order
- `excluded_stores` - Stores excluded from distribution
- `balance_threshold` - Threshold for balancing (default: 2)
- `store_balance_pairs` - Pairs of stores that can balance between each other

### `core/inventory_updater.py`
- `apply_transfers_to_inventory(file, previews, source_col, header_row)` → (bytes, warnings)
- `generate_updated_inventory_result(...)` → UpdatedInventoryResult

### `core/sales_parser.py`
- `parse_sales_file(file)` → SalesPriorityData

## UI Modules

### `ui/session_state.py`
- `init_session_state()` - Initializes session state
- `move_store_up/down(idx)` - Changes priority

### `ui/filters.py`
- `render_filters(df, prefix)` → DataFrame - Filters and shows UI
- `render_article_type_filter(df, prefix)` - Checkbox expander

### `ui/preview.py`
- `render_preview(previews, prefix)` - Shows distribution preview
- `generate_problems_excel(previews)` - Exports problems

### `ui/results.py`
- `render_results(results, updated_inventory)` - Download buttons (ZIP + individual files + updated inventory)

## Data Flow

```
Excel Upload → find_header_row() → pd.read_excel()
     ↓
render_filters() → filtered DataFrame
     ↓
StockDistributor/Balancer.preview() → TransferPreview[]
     ↓
render_preview() / .execute() → TransferResult[]
     ↓
render_results() → Download (ZIP + individual files)
     ↓
generate_updated_inventory() → UpdatedInventoryResult → Download (for next source)
```
