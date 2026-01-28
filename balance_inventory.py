#!/usr/bin/env python3
"""
Script 2: Balance inventory between stores

For each row:
- Find stores with > BALANCE_THRESHOLD items
- Distribute excess to stores with 0 inventory (priority order)
- If all stores have inventory, excess goes to Stock
- Takes from store with highest inventory first
"""

import pandas as pd
import os
from pathlib import Path
from datetime import datetime
from config import (
    STORE_PRIORITY, EXCLUDED_STORES, STOCK_COLUMN, PHOTO_STOCK_COLUMN,
    PRODUCT_NAME_COLUMN, VARIANT_COLUMN, INPUT_HEADER_ROW, OUTPUT_DIR,
    BALANCE_THRESHOLD
)

def get_stock_value(val):
    """Convert cell value to integer, treating NaN/empty as 0"""
    if pd.isna(val) or val == "" or val == "Остаток на складе":
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0

def balance_inventory(input_file: str):
    """
    Main balancing function
    
    For each product row:
    1. Find stores with inventory > threshold
    2. Calculate excess (qty - threshold)
    3. Distribute excess to stores with 0 (in priority order)
    4. Any remaining excess goes to Stock
    """
    print(f"Loading {input_file}...")
    df = pd.read_excel(input_file, header=INPUT_HEADER_ROW)
    
    # Skip header row
    df = df[df[PRODUCT_NAME_COLUMN].notna()].copy()
    df = df[df[PRODUCT_NAME_COLUMN] != ""].copy()
    
    # Filter stores by priority
    active_stores = [s for s in STORE_PRIORITY if s not in EXCLUDED_STORES and s in df.columns]
    
    print(f"Active stores: {len(active_stores)}")
    print(f"Balance threshold: {BALANCE_THRESHOLD}")
    print(f"Processing {len(df)} rows...")
    
    # Collect all transfers: {(sender, receiver): [(product, variant, qty), ...]}
    transfers = {}
    
    for idx, row in df.iterrows():
        product = row[PRODUCT_NAME_COLUMN]
        variant = row[VARIANT_COLUMN]
        
        # Build inventory map for this row
        store_inventory = {}
        for store in active_stores:
            store_inventory[store] = get_stock_value(row.get(store, 0))
        
        # Find stores with excess inventory (> threshold)
        stores_with_excess = [
            (store, qty) for store, qty in store_inventory.items() 
            if qty > BALANCE_THRESHOLD
        ]
        
        if not stores_with_excess:
            continue
        
        # Sort by quantity descending (take from highest first)
        stores_with_excess.sort(key=lambda x: x[1], reverse=True)
        
        # Find stores that need inventory (qty == 0)
        stores_needing = [
            store for store in active_stores 
            if store_inventory[store] == 0
        ]
        
        # Process each store with excess
        for sender_store, sender_qty in stores_with_excess:
            excess = sender_qty - BALANCE_THRESHOLD
            
            if excess <= 0:
                continue
            
            remaining_excess = excess
            
            # First: distribute to stores with 0 inventory
            for receiver_store in stores_needing:
                if remaining_excess <= 0:
                    break
                
                # Check if this store still needs (wasn't filled by another sender)
                if store_inventory[receiver_store] == 0:
                    # Transfer 1 item
                    sender_code = sender_store.split()[0]
                    receiver_code = receiver_store.split()[0]
                    
                    key = (sender_code, receiver_code)
                    if key not in transfers:
                        transfers[key] = []
                    transfers[key].append((product, variant, 1))
                    
                    store_inventory[receiver_store] = 1  # Mark as filled
                    remaining_excess -= 1
            
            # Second: any remaining excess goes to Stock
            if remaining_excess > 0:
                sender_code = sender_store.split()[0]
                key = (sender_code, "Сток")
                if key not in transfers:
                    transfers[key] = []
                transfers[key].append((product, variant, remaining_excess))
    
    # Create output directory
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Separate same-location transfers (sender == receiver shouldn't happen, but just in case)
    # and regular transfers
    regular_transfers = {}
    
    for (sender, receiver), items in transfers.items():
        if sender != receiver:
            regular_transfers[(sender, receiver)] = items
    
    # Generate output files
    print(f"\nGenerating output files...")
    files_created = []
    
    for (sender, receiver), items in regular_transfers.items():
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
        
        filename = f"{sender}_to_{receiver}_{timestamp}.xlsx"
        filepath = output_path / filename
        
        output_df.to_excel(filepath, index=False)
        files_created.append((filepath, len(items)))
        print(f"  Created: {filename} ({len(items)} items)")
    
    # Summary
    total_items = sum(len(items) for items in regular_transfers.values())
    print(f"\n=== Summary ===")
    print(f"Total files created: {len(files_created)}")
    print(f"Total transfer lines: {total_items}")
    
    return files_created

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python balance_inventory.py <input_file.xlsx>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    balance_inventory(input_file)
