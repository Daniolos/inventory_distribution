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

# Default balance threshold
DEFAULT_BALANCE_THRESHOLD = 2

# Column names (these are fixed based on input format)
STOCK_COLUMN = "Сток"
PHOTO_STOCK_COLUMN = "Фото склад"
PRODUCT_NAME_COLUMN = "Номенклатура"
VARIANT_COLUMN = "Характеристика"

# Filter columns (optional, used for filtering rows before processing)
COLLECTION_COLUMN = "Коллекция (сезон)"
ADDITIONAL_NAME_COLUMN = "Наименование_доп"

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
