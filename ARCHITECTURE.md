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

**Distribution Logic (phased, per product):**

A product participates only if its total size count falls within
`[min_product_sizes, max_product_sizes]`.

Each phase iterates stores in priority order and completes for every store before
the next phase begins (fair distribution).

1. **Phase 1 — Reach the size-count target**
   For each store: if `current_filled_sizes + transferable_sizes ≥ target_sizes_filled`,
   transfer 1 unit for each transferable size (where the store currently has 0 and
   stock is available). Otherwise the store is skipped entirely (all-or-nothing,
   `reason=target_not_reached`).
2. **Phase 2 — Top up to 2 units per filled size** (only if `units_per_size ≥ 2`)
   For every size the store has at 1 unit: transfer +1 if stock remains.
3. **Phase 3 — Top up to 3 units per filled size** (only if `units_per_size ≥ 3`)
   For every size the store has at 2 units: transfer +1 if stock remains.

The Outlet store has no special-case code — to fill it above the baseline, filter
the run to the outlet store and set `units_per_size` to the desired level.

### `core/balancer.py`
**InventoryBalancer** - Balances inventory between stores
- `preview(df, header_row)` → List[TransferPreview]
- `execute(df, header_row)` → List[TransferResult]

**Balancing Logic:**
- Excess (> threshold) goes directly to Stock
- Exception: Store pairs (125004↔125005, 125008↔129877) can balance between each other first
- Minimum sizes rule applies to paired transfers:
  - If partner has 0-1 sizes AND product has 4+ sizes → need 3+ transferable sizes
  - If sender can provide 3+ sizes: all transfer to partner
  - If sender can provide <3 sizes: all to Stock instead
- If partner has 2+ sizes: normal rule (1 item per variant where partner has 0)

(The balancer rule is independent of the distributor's target-sizes logic and uses
balancer-local constants in `core/balancer.py`.)

### `core/config.py`
- `DEFAULT_STORE_PRIORITY` - Default store order
- `DEFAULT_EXCLUDED_STORES` - Default excluded stores
- `STORE_BALANCE_PAIRS` - Store pairs that can balance between each other
- `DEFAULT_BALANCE_THRESHOLD` - Balancer threshold (default: 2)
- `DEFAULT_TARGET_SIZES_FILLED` - Distributor: minimum sizes the store must end up with (default: 3)
- `DEFAULT_UNITS_PER_SIZE` - Distributor: units per filled size (default: 1)
- `MAX_UNITS_PER_SIZE` - Distributor: UI cap for units per size (default: 3)
- `DEFAULT_MIN_PRODUCT_SIZES` / `DEFAULT_MAX_PRODUCT_SIZES` - Distributor: product size-count range filter (default: 1–99)

### `core/file_loader.py`
- `find_header_row(file)` - Auto-detects header row
- `load_excel_with_header(file)` - Loads with header detection

### `core/filters.py`
- `extract_article_name(nomenclature)` - Extracts article name
- `apply_all_filters(df, ...)` - Filters DataFrame

### `core/models.py`
Dataclasses: `Transfer`, `TransferPreview`, `TransferResult`, `DistributionConfig`, `UpdatedInventoryResult`

**Shared Utility Functions:**
- `get_stock_value(val)` - Convert cell value to int (used by both distributor and balancer)
- `count_sizes_with_stock(rows, store)` - Count sizes a store has for a product
- `should_apply_min_sizes_rule(store_sizes, total_sizes)` - Check if min sizes rule applies

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
