# Inventory Distribution App - Requirements for Claude Code

## Project Overview

Two working Python scripts for inventory distribution already exist. These should now be converted into a user-friendly web app that can be operated by non-technical users.

---

## Existing Code

### Project Files

```
inventory_distribution/
├── config.py                    # Configuration (priorities, exclusions)
├── distribute_stock.py  # Stock → Stores distribution
├── balance_inventory.py # Balance inventory
├── test_scenarios.xlsx          # Test file with 8 scenarios
├── test_data.py                 # Generator for test file
└── README.md
```

### Script 1: Stock → Stores (`distribute_stock.py`)

**Function:** Distributes inventory from "Сток" (Stock) or "Фото склад" (Photo Stock) to stores.

**Logic:**
- Goes through each row in the input Excel
- For each store with inventory = 0: Distributes 1 item
- Follows the priority order from `config.py`
- Skips excluded stores
- Distributes maximum as many items as available in Stock

**Parameters:**
- `source`: "stock" (Сток) or "photo" (Фото склад)

### Script 2: Balance Inventory (`balance_inventory.py`)

**Function:** Balances inventory between stores.

**Logic:**
- Finds stores with inventory > BALANCE_THRESHOLD (default: 2)
- Takes from store with highest inventory first
- Distributes surplus to stores with inventory = 0 (priority order)
- If all stores have inventory: remainder goes to Stock

### Configuration (`config.py`)

```python
STORE_PRIORITY = [
    "125007 MSK-PC-Гагаринский",      # Highest priority
    "125008 MSK-PC-РИО Ленинский",
    "129877 MSK-PC-Мега 1 Теплый Стан",
    "130143 MSK-PCM-Мега 2 Химки",
    "150002 MSK-DV-Капитолий",
    "125009 NNV-PC-Фантастика",
    "125011 SPB-PC-Мега 2 Парнас",
    "125004 EKT-PC-Гринвич",
    "125005 EKT-PC-Мега",
    "125006 KZN-PC-Мега",
    "125839 - MSK-PC-Outlet Белая Дача",  # Lowest priority
]

EXCLUDED_STORES = []  # Stores that receive nothing

BALANCE_THRESHOLD = 2  # Stores with > 2 items will be balanced
```

### Input Format (Excel)

- Header in row 7 (0-indexed: row 6)
- Columns for product identification: `Номенклатура`, `Характеристика`
- Columns for stores: e.g. `125007 MSK-PC-Гагаринский`
- Columns for warehouse: `Сток`, `Фото склад`
- Values: Integer (quantity) or empty (= 0)

### Output Format (Excel)

Separate files per sender-receiver combination:
- Filename: `{Sender}_to_{Receiver}_{Timestamp}.xlsx`
- Columns: `Артикул`, `Код номенклатуры`, `Номенклатура`, `Характеристика`, `Назначение`, `Серия`, `Код упаковки`, `Упаковка`, `Количество`
- Only `Номенклатура`, `Характеристика`, `Количество` are filled

---

## Streamlit App Requirements

### 1. Basic UI Elements

#### File Upload
- Drag & Drop zone for Excel file (.xlsx)
- Display filename and row count after upload
- Validation: Check if expected columns are present

#### Script Selection
- Radio Buttons or Tabs:
  - "Script 1: Stock → Stores Distribution"
  - "Script 2: Balance Inventory"

#### Script 1 Specific Options
- Dropdown/Radio: Select source
  - "Сток (Stock)"
  - "Фото склад (Photo Stock)"

#### Script 2 Specific Options
- Number Input: Balance Threshold (default: 2)

### 2. Configuration (for both scripts)

#### Priority Editor
- Sortable list of all stores
- Drag & Drop for reordering OR Up/Down buttons
- Display current priority as numbered list

#### Exclusion Editor
- Checkboxes for each store
- Selected stores are excluded from distribution

### 3. Preview / Intermediate Step Display (IMPORTANT!)

**Before execution:**
- Button "Generate Preview"
- Shows planned assignments per input row

**Display:**
```
Row 1: Test Product A / Size M
  └─ Сток → 125007: 1 item
  └─ Сток → 125008: 1 item
  └─ Сток → 129877: 1 item

Row 2: Test Product B / Size L
  └─ Сток → 129877: 1 item
  └─ Сток → 130143: 1 item

Row 3: Test Product C / Size S
  └─ (no distribution - Stock = 0)
```

**Features:**
- Expandable/Collapsible per row (for many rows)
- Filter: Show only rows with assignments
- Search field: Filter by product name
- Summary at top: "X rows, Y total assignments"

### 4. Execution and Download

#### Execute Button
- "Generate Transfers"
- Progress bar during processing
- Success message with summary

#### Download Section
- List of all generated files
- "Download All as ZIP" button
- Individual files clickable for download
- Display: Filename + number of entries

### 5. Additional Features

#### Validation & Error Handling
- Warning for unknown columns in input
- Error display when store from config doesn't exist in input
- Info when no distributions are possible

#### Session State
- Configuration is preserved during session
- Option: Export/import configuration as JSON

#### Help/Documentation
- Sidebar or expander with logic explanation
- Tooltip for configuration options

---

## Technical Requirements

### Deployment

**Target: Streamlit Community Cloud**
- Free hosting
- Deployment directly from GitHub
- No server configuration needed

**Repository Structure:**
```
inventory-distribution-app/
├── app.py                  # Streamlit main application
├── core/
│   ├── __init__.py
│   ├── distributor.py      # Script 1 logic (refactored)
│   ├── balancer.py         # Script 2 logic (refactored)
│   └── config.py           # Default configuration
├── requirements.txt        # Dependencies
├── .streamlit/
│   └── config.toml         # Streamlit config (theme etc.)
└── README.md
```

### Dependencies

```
streamlit>=1.28.0
pandas>=2.0.0
openpyxl>=3.1.0
```

### Code Refactoring

The existing logic from `distribute_stock.py` and `balance_inventory.py` should be refactored into classes/functions that:
- Accept input DataFrame directly (not file path)
- Accept configuration as parameter (not import from config.py)
- Return intermediate steps as data structure (for preview)
- Return output as list of DataFrames (not save directly)

**Example Interface:**

```python
class StockDistributor:
    def __init__(self, config: DistributionConfig):
        self.config = config

    def preview(self, df: pd.DataFrame) -> list[TransferPreview]:
        """Generates preview of assignments without executing"""
        pass

    def execute(self, df: pd.DataFrame) -> list[TransferResult]:
        """Executes distribution and returns results"""
        pass

@dataclass
class TransferPreview:
    row_index: int
    product_name: str
    variant: str
    transfers: list[Transfer]  # [(sender, receiver, qty), ...]

@dataclass
class TransferResult:
    sender: str
    receiver: str
    filename: str
    data: pd.DataFrame
```

---

## Nice-to-Have (later)

These features are optional and can be added in later iterations:

1. **Proximity-based Distribution**
   - Prefer nearby stores
   - Define distance matrix between stores

2. **History/Audit Log**
   - Log of executed distributions
   - Who distributed what and when

3. **Automatic Detection**
   - Automatically detect input format
   - Column mapping UI when format differs

4. **Multi-Language Support**
   - German/Russian/English UI

---

## Test Data

The file `test_scenarios.xlsx` contains 8 predefined test scenarios covering all edge cases:

| # | Scenario | Expected Result |
|---|----------|-----------------|
| S1 | Stock=5, all stores empty | 5 stores receive 1 each |
| S2 | Stock=3, some already have | Only empty ones receive |
| S3 | Stock=0 | No distribution |
| S4 | All already have 1 | No distribution |
| S5 | One store has >2 | Surplus is distributed |
| S6 | Multiple >2 | Highest inventory first |
| S7 | Surplus, all full | Remainder goes to Stock |
| S8 | Photo Stock instead of Stock | Works with photo flag |

These scenarios should also be testable in the app (e.g., "Test with example data" button).

---

## Priority Summary

1. **Must Have:**
   - File Upload + Validation
   - Script selection (Script 1 / Script 2)
   - Configuration (Priorities, Exclusions, Threshold)
   - Preview of assignments per row
   - Download generated files

2. **Should Have:**
   - Progress Bar
   - Filter/Search in preview
   - Config Export/Import

3. **Nice to Have:**
   - Proximity-based distribution
   - Multi-Language
