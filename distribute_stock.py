#!/usr/bin/env python3
"""
Script 1: Distribute inventory from Stock (Сток) or Photo Stock (Фото склад) to stores

For each row:
- Takes items from Stock (or Photo Stock)
- Distributes 1 item to each store that has 0 inventory
- Follows priority order, respects exclusions
- Generates transfer files grouped by sender-receiver combination
"""

import pandas as pd
import os
from pathlib import Path
from datetime import datetime
from config import (
    STORE_PRIORITY, EXCLUDED_STORES, STOCK_COLUMN, PHOTO_STOCK_COLUMN,
    PRODUCT_NAME_COLUMN, VARIANT_COLUMN, INPUT_HEADER_ROW, OUTPUT_DIR
)

def get_stock_value(val):
    """Convert cell value to integer, treating NaN/empty as 0"""
    if pd.isna(val) or val == "" or val == "Остаток на складе":
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0

def distribute_from_source(input_file: str, source: str = "stock"):
    """
    Main distribution function
    
    Args:
        input_file: Path to input Excel file
        source: "stock" for Сток, "photo" for Фото склад
    """
    source_column = STOCK_COLUMN if source == "stock" else PHOTO_STOCK_COLUMN
    source_name = "Сток" if source == "stock" else "Фото"
    
    print(f"Loading {input_file}...")
    df = pd.read_excel(input_file, header=INPUT_HEADER_ROW)
    
    # Skip header row with "Остаток на складе"
    df = df[df[PRODUCT_NAME_COLUMN].notna()].copy()
    df = df[df[PRODUCT_NAME_COLUMN] != ""].copy()
    
    # Filter stores by priority (excluding excluded ones)
    active_stores = [s for s in STORE_PRIORITY if s not in EXCLUDED_STORES and s in df.columns]
    
    print(f"Active stores: {len(active_stores)}")
    print(f"Processing {len(df)} rows...")
    
    # Collect all transfers: {(sender, receiver): [(product, variant, qty), ...]}
    transfers = {}
    
    for idx, row in df.iterrows():
        product = row[PRODUCT_NAME_COLUMN]
        variant = row[VARIANT_COLUMN]
        source_qty = get_stock_value(row.get(source_column, 0))
        
        if source_qty <= 0:
            continue
        
        remaining = source_qty
        
        for store in active_stores:
            if remaining <= 0:
                break
            
            store_qty = get_stock_value(row.get(store, 0))
            
            # Only distribute to stores with 0 inventory
            if store_qty == 0:
                # Transfer 1 item
                key = (source_name, store)
                if key not in transfers:
                    transfers[key] = []
                transfers[key].append((product, variant, 1))
                remaining -= 1
    
    # Create output directory
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generate output files
    print(f"\nGenerating output files...")
    files_created = []
    
    for (sender, receiver), items in transfers.items():
        # Create DataFrame for this transfer
        output_df = pd.DataFrame({
            "Артикул": [""] * len(items),
            "Код номенклатуры": [""] * len(items),
            "Номенклатура": [item[0] for item in items],
            "Характеристика": [item[1] for item in items],
            "Назначение": [""] * len(items),
            "Серия": [""] * len(items),
            "Код упаковки": [""] * len(items),
            "Упаковка": [""] * len(items),
            "Количество": [item[2] for item in items],
        })
        
        # Extract store number from name (e.g., "125007 MSK-PC-..." -> "125007")
        receiver_code = receiver.split()[0] if receiver != source_name else "Сток"
        
        filename = f"{source_name}_to_{receiver_code}_{timestamp}.xlsx"
        filepath = output_path / filename
        
        output_df.to_excel(filepath, index=False)
        files_created.append((filepath, len(items)))
        print(f"  Created: {filename} ({len(items)} items)")
    
    # Summary
    total_items = sum(len(items) for items in transfers.values())
    print(f"\n=== Summary ===")
    print(f"Total files created: {len(files_created)}")
    print(f"Total items distributed: {total_items}")
    
    return files_created

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python distribute_stock.py <input_file.xlsx> [stock|photo]")
        print("  stock = distribute from Сток (default)")
        print("  photo = distribute from Фото склад")
        sys.exit(1)
    
    input_file = sys.argv[1]
    source = sys.argv[2] if len(sys.argv) > 2 else "stock"
    
    if source not in ["stock", "photo"]:
        print("Error: source must be 'stock' or 'photo'")
        sys.exit(1)
    
    distribute_from_source(input_file, source)
