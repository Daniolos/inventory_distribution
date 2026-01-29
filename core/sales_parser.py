"""Parser for hierarchical sales Excel files."""

import pandas as pd
from typing import Optional

from .models import SalesPriorityData, ProductSalesData, StoreSales, extract_store_id


def extract_product_code_from_sales(name: str) -> Optional[str]:
    """
    Extract product code from sales file product name.

    Extracts the code after the LAST underscore:
    - "_P1 60105_P1 60105" → "P1 60105"
    - "Джемпер_C5 50706.5037/7015" → "C5 50706.5037/7015"

    Returns None for store rows (start with digits) or header rows.

    Args:
        name: Raw cell value from first column

    Returns:
        Extracted code or None if not a product row
    """
    if not name or not isinstance(name, str):
        return None

    name = name.strip()

    # Store rows start with digits - not a product
    if name and name[0].isdigit():
        return None

    # Must contain underscore
    if "_" not in name:
        return None

    # Extract code after LAST underscore
    parts = name.rsplit("_", 1)
    if len(parts) == 2 and parts[1]:
        return parts[1].strip()

    return None


def extract_product_code_from_input(nomenclature: str) -> Optional[str]:
    """
    Extract product code from input file Номенклатура column.

    The input file format has product names like:
    "Мужские шорты_C3 34770.4007/6214"

    Args:
        nomenclature: Value from Номенклатура column

    Returns:
        Extracted code (e.g., "C3 34770.4007/6214") or None
    """
    if not nomenclature or not isinstance(nomenclature, str):
        return None

    if "_" not in nomenclature:
        return None

    # Split on first underscore and take everything after
    parts = nomenclature.split("_", 1)
    if len(parts) == 2 and parts[1]:
        return parts[1]

    return None


def parse_sales_file(file) -> SalesPriorityData:
    """
    Parse hierarchical sales Excel file.

    The file has a hierarchical structure:
    - Product rows start with "_" (e.g., "_C5 21354.2110/1010_C5 21354.2110/1010")
    - Store rows follow with store ID + name (e.g., "0130143 MSK-PCM-Мега 2 Химки")
    - Column 0: Product/Store name
    - Column 3: Quantity (sales)

    Args:
        file: File-like object (uploaded Excel)

    Returns:
        SalesPriorityData with all products and their store sales

    Raises:
        ValueError: If file format is invalid
    """
    # Read without header to process hierarchical structure
    df = pd.read_excel(file, header=None)

    result = SalesPriorityData()
    current_product: Optional[ProductSalesData] = None

    # Iterate through rows
    for idx, row in df.iterrows():
        cell_value = row.iloc[0] if len(row) > 0 else None  # First column
        if pd.isna(cell_value):
            continue

        cell_str = str(cell_value).strip()

        # Skip header rows and empty strings
        if not cell_str or cell_str in ("Номенклатура", "Склад"):
            continue

        # Check if this is a product row (starts with "_")
        product_code = extract_product_code_from_sales(cell_str)
        if product_code:
            # Save previous product if exists
            if current_product:
                result.products[current_product.product_code] = current_product

            # Get total quantity (column 3)
            quantity = 0
            if len(row) > 3 and pd.notna(row.iloc[3]):
                try:
                    quantity = int(float(row.iloc[3]))
                except (ValueError, TypeError):
                    quantity = 0

            # Start new product
            current_product = ProductSalesData(
                product_code=product_code,
                raw_name=cell_str,
                total_quantity=quantity,
                store_sales=[]
            )
            continue

        # Check if this is a store row (starts with digits)
        store_id = extract_store_id(cell_str)
        if store_id and current_product:
            # Get quantity (column 3)
            quantity = 0
            if len(row) > 3 and pd.notna(row.iloc[3]):
                try:
                    quantity = int(float(row.iloc[3]))
                except (ValueError, TypeError):
                    quantity = 0

            current_product.store_sales.append(StoreSales(
                store_id=store_id,
                store_name=cell_str,
                quantity=quantity
            ))

    # Save last product
    if current_product:
        result.products[current_product.product_code] = current_product

    return result
