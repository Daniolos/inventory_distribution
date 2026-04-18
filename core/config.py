"""Default configuration values."""

# Default store priority (can be modified in UI)
DEFAULT_STORE_PRIORITY = [
    "125006 KZN-PC-Мега",
    "125007 MSK-PC-Гагаринский",
    "125011 SPB-PC-Мега 2 Парнас",
    "125005 EKT-PC-Мега",
    "125008 MSK-PC-РИО Ленинский",
    "125009 NNV-PC-Фантастика",
    "125004 EKT-PC-Гринвич",
    "129877 MSK-PC-Мега 1 Теплый Стан",
    "130143 MSK-PCM-Мега 2 Химки",
    "150002 MSK-DV-Капитолий",
    "125839 - MSK-PC-Outlet Белая Дача",
]

# Default excluded stores
DEFAULT_EXCLUDED_STORES = []

# Store pairs that can balance between each other before sending to Stock
# Each pair is a tuple of two store ID prefixes (the numeric codes)
STORE_BALANCE_PAIRS: list[tuple[str, str]] = [
    ("125004", "125005"),  # EKT-PC-Гринвич <-> EKT-PC-Мега
    ("125008", "129877"),  # MSK-PC-РИО Ленинский <-> MSK-PC-Мега 1 Теплый Стан
]

# Default balance threshold (used by InventoryBalancer)
DEFAULT_BALANCE_THRESHOLD = 2

# Stock distribution defaults
DEFAULT_TARGET_SIZES_FILLED = 3  # Store must end up with at least this many sizes filled
DEFAULT_UNITS_PER_SIZE = 1       # Units per filled size after distribution
MAX_UNITS_PER_SIZE = 3           # UI cap for units_per_size
DEFAULT_MIN_PRODUCT_SIZES = 1    # Product size-count range filter: lower bound
DEFAULT_MAX_PRODUCT_SIZES = 99   # Product size-count range filter: upper bound

# Column names (these are fixed based on input format)
STOCK_COLUMN = "Сток"
PHOTO_STOCK_COLUMN = "Фото склад"
PRODUCT_NAME_COLUMN = "Номенклатура"
VARIANT_COLUMN = "Характеристика"

# Filter columns (optional, used for filtering rows before processing)
COLLECTION_COLUMN = "Коллекция (сезон)"
ADDITIONAL_NAME_COLUMN = "Наименование_доп"
ARTICLE_TYPE_FILTER_LABEL = "Тип артикула"

# Output columns for transfer files
OUTPUT_COLUMNS = [
    "Артикул",
    "Код номенклатуры",
    "Номенклатура",
    "Характеристика",
    "Назначение",
    "Серия",
    "Код упаковки",
    "Упаковка",
    "Количество",
]
