"""Inventory balancing logic - redistributes excess inventory between stores."""

import pandas as pd
from datetime import datetime
from typing import Optional

from .models import (
    Transfer,
    TransferPreview,
    TransferResult,
    DistributionConfig,
    SalesPriorityData,
    build_store_id_map,
)
from .sales_parser import extract_product_code_from_input


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
    - Excess goes directly to Stock (no distribution to other stores)
    - Exception: Store pairs can balance between each other first
    - Takes from store with highest inventory first
    """

    def __init__(
        self,
        config: DistributionConfig,
        sales_data: Optional[SalesPriorityData] = None
    ):
        self.config = config
        self.sales_data = sales_data
        # Build store ID to name mapping for matching sales data
        self._store_id_map = build_store_id_map(config.store_priority)

    def _get_product_priority(
        self,
        product_name: str,
        available_stores: list[str]
    ) -> tuple[list[str], bool]:
        """
        Get store priority for a specific product.

        Args:
            product_name: Product name from Номенклатура column
            available_stores: List of stores that exist in the DataFrame

        Returns:
            Tuple of (active_store_list_in_priority_order, uses_fallback)
        """
        # Default: use static priority
        fallback_priority = [s for s in self.config.active_stores if s in available_stores]

        if not self.sales_data:
            return fallback_priority, False

        # Extract product code from input file format
        product_code = extract_product_code_from_input(product_name)
        if not product_code:
            return fallback_priority, True

        # Look up in sales data
        priority, found = self.sales_data.get_product_priority(
            product_code,
            self.config.store_priority,
            self._store_id_map
        )

        if not found:
            return fallback_priority, True

        # Filter to available stores only and maintain sales-based order
        active_priority = [s for s in priority if s in available_stores and s in self.config.active_stores]

        # Add any stores that weren't in sales data but are in available/active
        for store in fallback_priority:
            if store not in active_priority:
                active_priority.append(store)

        return active_priority, False

    def _find_store_by_code(self, store_code: str, stores: list[str]) -> Optional[str]:
        """
        Find full store name by its code prefix.

        Args:
            store_code: Store ID prefix (e.g., "125004")
            stores: List of full store names to search

        Returns:
            Full store name if found, None otherwise
        """
        for store in stores:
            if store.startswith(store_code + " "):
                return store
        return None

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

        # Get all stores that exist in the DataFrame (for analysis)
        available_stores = [
            s for s in self.config.store_priority
            if s in df_filtered.columns
        ]

        previews = []

        for idx, (original_idx, row) in enumerate(df_filtered.iterrows()):
            product = row[self.config.product_name_column]
            variant = row.get(self.config.variant_column, "")
            product_name = str(product) if pd.notna(product) else ""

            # Calculate Excel row: header_row (0-based) + 3 + original_idx
            # Breakdown: +1 for 1-based Excel, +1 for header row, +1 for skipped sub-header row
            # Using original_idx (pandas index) instead of idx to preserve correct row number after filtering
            excel_row = header_row + 3 + original_idx

            # Get product-specific store priority
            product_stores, uses_fallback = self._get_product_priority(product_name, available_stores)

            preview = TransferPreview(
                row_index=excel_row,  # Excel row number for display
                product_name=product_name,
                variant=str(variant) if pd.notna(variant) else "",
                uses_fallback_priority=uses_fallback and self.sales_data is not None,
            )

            # Build inventory map for this row
            store_inventory = {}
            for store in product_stores:
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

            # Create a working copy of inventory for tracking paired store balancing
            working_inventory = store_inventory.copy()

            # Process each store with excess
            for sender_store, sender_qty in stores_with_excess:
                excess = sender_qty - self.config.balance_threshold

                if excess <= 0:
                    continue

                remaining_excess = excess
                sender_code = sender_store.split()[0]

                # Check if sender is in a balance pair
                partner_code = self.config.get_paired_store(sender_code)

                if partner_code:
                    # Find partner store in available stores
                    partner_store = self._find_store_by_code(partner_code, product_stores)

                    if (partner_store and
                            partner_store not in self.config.excluded_stores):
                        partner_qty = working_inventory.get(partner_store, 0)

                        # Only send to partner if they have 0 inventory
                        if partner_qty == 0 and remaining_excess > 0:
                            preview.transfers.append(Transfer(
                                sender=sender_code,
                                receiver=partner_store,
                                quantity=1
                            ))
                            working_inventory[partner_store] = 1
                            remaining_excess -= 1

                # All remaining excess goes to Stock (paired or not)
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
