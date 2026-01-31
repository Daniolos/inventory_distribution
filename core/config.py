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

# Default balance threshold
DEFAULT_BALANCE_THRESHOLD = 2

# Minimum sizes rule configuration (shared between distributor and balancer)
# Rule: If store has 0-1 sizes of a product with 4+ total sizes,
# only transfer if 3+ sizes are available (all-or-nothing)
MIN_SIZES_THRESHOLD = 2  # If store has < this many sizes, apply min sizes rule
MIN_SIZES_TO_ADD = 3     # Minimum number of different sizes required for transfer
MIN_PRODUCT_SIZES_FOR_RULE = 4  # Product must have at least this many sizes

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
