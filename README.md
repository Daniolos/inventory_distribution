# Inventory Distribution Scripts

Two Python scripts for automatic inventory distribution to stores.

## Prerequisites

- Python 3.8+
- pandas: `pip install pandas openpyxl`

## Script 1: Stock → Stores Distribution

Distributes inventory from **Сток** or **Фото склад** to stores with 0 inventory.

### Usage

```bash
# Distribute from Сток (default)
python distribute_stock.py "data/Остатки + Сезон.xlsx" stock

# Distribute from Фото склад
python distribute_stock.py "data/Остатки + Сезон.xlsx" photo
```

### Logic
- Goes through each row
- For each store with inventory = 0: distribute 1 item
- Follows the priority order in `config.py`
- Respects excluded stores

---

## Script 2: Balance Inventory

Balances inventory between stores.

### Usage

```bash
python balance_inventory.py "data/Остатки + Сезон.xlsx"
```

### Logic
- Finds stores with > 2 items (configurable)
- Takes from store with the most items first
- Distributes to stores with 0 inventory
- Remainder goes back to Stock

---

## Configuration (config.py)

```python
# Store priority (top = highest priority)
STORE_PRIORITY = [
    "125007 MSK-PC-Гагаринский",
    "125008 MSK-PC-РИО Ленинский",
    # ... more stores
]

# Excluded stores
EXCLUDED_STORES = [
    # "125839 - MSK-PC-Outlet Белая Дача",  # Uncomment to exclude
]

# Threshold for balancing (Script 2)
BALANCE_THRESHOLD = 2  # Stores with > 2 items will be balanced
```

---

## Output

All output files are created in the `output/` folder:

- Format: `{Sender}_to_{Receiver}_{Timestamp}.xlsx`
- Examples:
  - `Сток_to_125007_20260128_143000.xlsx`
  - `125839_to_Сток_20260128_143000.xlsx`

### Output Columns

| Column | Filled |
|--------|--------|
| Артикул | ❌ |
| Код номенклатуры | ❌ |
| Номенклатура | ✅ |
| Характеристика | ✅ |
| Назначение | ❌ |
| Серия | ❌ |
| Код упаковки | ❌ |
| Упаковка | ❌ |
| Количество | ✅ |

---

## Future Enhancements

- [ ] Proximity-based distribution (prefer nearby stores)
- [ ] GUI for easier operation
- [ ] Automatic email notification after execution
