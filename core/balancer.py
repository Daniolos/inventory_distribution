"""Inventory balancing logic - redistributes excess inventory between stores."""

import pandas as pd
from datetime import datetime
from typing import Optional

from .models import Transfer, TransferPreview, TransferResult, DistributionConfig


def get_stock_value(val) -> int:
    """Convert cell value to integer, treating NaN/empty as 0."""
    if pd.isna(val) or val == "" or val == "Остаток на складе":
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


class InventoryBalancer:
    """
    Balances inventory between stores.

    For each row:
    - Find stores with > threshold items
    - Distribute excess to stores with 0 inventory (priority order)
    - If all stores have inventory, excess goes to Stock
    - Takes from store with highest inventory first
    """

    def __init__(self, config: DistributionConfig):
        self.config = config

    def preview(self, df: pd.DataFrame, header_row: int = 0) -> list[TransferPreview]:
        """
        Generate preview of balancing operations without executing.

        Args:
            df: Input DataFrame (already loaded with correct header row)
            header_row: 0-indexed header row in Excel (for displaying correct Excel row numbers)

        Returns:
            List of TransferPreview objects showing planned redistributions
        """
        # Filter valid rows
        df_filtered = df[df[self.config.product_name_column].notna()].copy()
        df_filtered = df_filtered[df_filtered[self.config.product_name_column] != ""]

        # Get active stores that exist in the DataFrame
        active_stores = [
            s for s in self.config.active_stores
            if s in df_filtered.columns
        ]

        previews = []

        for idx, (original_idx, row) in enumerate(df_filtered.iterrows()):
            product = row[self.config.product_name_column]
            variant = row.get(self.config.variant_column, "")

            # Calculate Excel row: header_row (0-based) + 2 (1 for 1-based, 1 for data after header) + original_idx
            # Using original_idx (pandas index) instead of idx to preserve correct row number after filtering
            excel_row = header_row + 2 + original_idx

            preview = TransferPreview(
                row_index=excel_row,  # Excel row number for display
                product_name=str(product) if pd.notna(product) else "",
                variant=str(variant) if pd.notna(variant) else "",
            )

            # Build inventory map for this row
            store_inventory = {}
            for store in active_stores:
                store_inventory[store] = get_stock_value(row.get(store, 0))

            # Find stores with excess inventory (> threshold)
            stores_with_excess = [
                (store, qty) for store, qty in store_inventory.items()
                if qty > self.config.balance_threshold
            ]

            if not stores_with_excess:
                previews.append(preview)
                continue

            # Sort by quantity descending (take from highest first)
            stores_with_excess.sort(key=lambda x: x[1], reverse=True)

            # Find stores that need inventory (qty == 0)
            stores_needing = [
                store for store in active_stores
                if store_inventory[store] == 0
            ]

            # Create a working copy of inventory for tracking
            working_inventory = store_inventory.copy()

            # Process each store with excess
            for sender_store, sender_qty in stores_with_excess:
                excess = sender_qty - self.config.balance_threshold

                if excess <= 0:
                    continue

                remaining_excess = excess
                sender_code = sender_store.split()[0]

                # First: distribute to stores with 0 inventory
                for receiver_store in stores_needing:
                    if remaining_excess <= 0:
                        break

                    # Check if this store still needs (wasn't filled by another sender)
                    if working_inventory[receiver_store] == 0:
                        preview.transfers.append(Transfer(
                            sender=sender_code,
                            receiver=receiver_store,
                            quantity=1
                        ))
                        working_inventory[receiver_store] = 1  # Mark as filled
                        remaining_excess -= 1

                # Second: any remaining excess goes to Stock
                if remaining_excess > 0:
                    preview.transfers.append(Transfer(
                        sender=sender_code,
                        receiver="Сток",
                        quantity=remaining_excess
                    ))

            previews.append(preview)

        return previews

    def execute(self, df: pd.DataFrame, header_row: int = 0) -> list[TransferResult]:
        """
        Execute balancing and return transfer results.

        Args:
            df: Input DataFrame (already loaded with correct header row)
            header_row: 0-indexed header row in Excel

        Returns:
            List of TransferResult objects ready for download
        """
        # Get preview (contains all transfers)
        previews = self.preview(df, header_row)

        # Group transfers by (sender, receiver)
        transfers_grouped: dict[tuple[str, str], list[tuple[str, str, int]]] = {}

        for preview in previews:
            for transfer in preview.transfers:
                # Extract receiver code
                if transfer.receiver == "Сток":
                    receiver_code = "Сток"
                else:
                    receiver_code = transfer.receiver.split()[0]

                key = (transfer.sender, receiver_code)
                if key not in transfers_grouped:
                    transfers_grouped[key] = []
                transfers_grouped[key].append((
                    preview.product_name,
                    preview.variant,
                    transfer.quantity
                ))

        # Filter out self-transfers (shouldn't happen, but safety check)
        regular_transfers = {
            k: v for k, v in transfers_grouped.items()
            if k[0] != k[1]
        }

        # Create results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = []

        for (sender, receiver), items in regular_transfers.items():
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

            filename = f"{sender}_to_{receiver}_{timestamp}.xlsx"

            results.append(TransferResult(
                sender=sender,
                receiver=receiver,
                filename=filename,
                data=output_df
            ))

        return results
