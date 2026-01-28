# Configuration for inventory distribution scripts

# Store columns in the input Excel file (in priority order for distribution)
# Stores at the top get items first
STORE_PRIORITY = [
    "125007 MSK-PC-Гагаринский",
    "125008 MSK-PC-РИО Ленинский",
    "129877 MSK-PC-Мега 1 Теплый Стан",
    "130143 MSK-PCM-Мега 2 Химки",
    "150002 MSK-DV-Капитолий",
    "125009 NNV-PC-Фантастика",
    "125011 SPB-PC-Мега 2 Парнас",
    "125004 EKT-PC-Гринвич",
    "125005 EKT-PC-Мега",
    "125006 KZN-PC-Мега",
    "125839 - MSK-PC-Outlet Белая Дача",
]

# Stores to EXCLUDE from distribution (they receive nothing)
EXCLUDED_STORES = [
    # "125839 - MSK-PC-Outlet Белая Дача",  # Example: uncomment to exclude
]

# Source columns
STOCK_COLUMN = "Сток"
PHOTO_STOCK_COLUMN = "Фото склад"

# Product identification columns
PRODUCT_NAME_COLUMN = "Номенклатура"
VARIANT_COLUMN = "Характеристика"

# For Script 2: Threshold - stores with MORE than this get redistributed
BALANCE_THRESHOLD = 2

# Input file settings
INPUT_HEADER_ROW = 6  # 0-indexed: row 7 in Excel

# Output directory
OUTPUT_DIR = "output"
