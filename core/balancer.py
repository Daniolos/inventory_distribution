"""Inventory balancing logic - redistributes excess inventory between stores."""

import pandas as pd
from datetime import datetime
from typing import Optional
from collections import defaultdict

from .models import (
    Transfer,
    TransferPreview,
    TransferResult,
    DistributionConfig,
    SalesPriorityData,
    build_store_id_map,
    get_stock_value,
    count_sizes_with_stock,
    should_apply_min_sizes_rule,
)
from .sales_parser import extract_product_code_from_input
from .config import MIN_SIZES_TO_ADD


class InventoryBalancer:
    """
    Balances inventory between stores.

    For each row:
    - Find stores with > threshold items
    - Excess goes directly to Stock (no distribution to other stores)
    - Exception: Store pairs can balance between each other first
      - Minimum sizes rule applies: partner needs 3+ sizes if they have 0-1
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

    def _analyze_products(
        self,
        df: pd.DataFrame,
        available_stores: list[str],
        header_row: int = 0
    ) -> dict:
        """
        Analyze inventory by product to understand size distribution.

        Returns:
            Dict with product name as key, containing:
            - rows: list of row dicts with variant, store_quantities, excel_row, original_idx
            - total_sizes: count of all sizes for this product
        """
        product_data: dict = defaultdict(lambda: {"rows": [], "total_sizes": 0})

        for original_idx, row in df.iterrows():
            product = row[self.config.product_name_column]
            if pd.isna(product) or product == "":
                continue

            product_name = str(product)
            variant = row.get(self.config.variant_column, "")
            variant_str = str(variant) if pd.notna(variant) else ""

            # Build store quantities for this row
            store_quantities = {}
            for store in available_stores:
                store_quantities[store] = get_stock_value(row.get(store, 0))

            excel_row = header_row + 3 + original_idx

            product_data[product_name]["rows"].append({
                "excel_row": excel_row,
                "original_idx": original_idx,
                "variant": variant_str,
                "store_quantities": store_quantities,
            })

        # Calculate total sizes per product
        for product_name, data in product_data.items():
            data["total_sizes"] = len(data["rows"])

        return dict(product_data)

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

        # Analyze products for minimum sizes rule
        product_data = self._analyze_products(df_filtered, available_stores, header_row)

        # Track which product/partner combinations have been evaluated for min sizes rule
        # Key: (product_name, partner_store), Value: bool (can_transfer_to_partner)
        partner_transfer_decisions: dict[tuple[str, str], bool] = {}

        # Track working inventory across all rows (for paired store balancing)
        # Key: (product_name, variant, store), Value: current inventory
        working_inventory: dict[tuple[str, str, str], int] = {}

        # Initialize working inventory from product_data
        for product_name, data in product_data.items():
            for row_data in data["rows"]:
                variant = row_data["variant"]
                for store, qty in row_data["store_quantities"].items():
                    working_inventory[(product_name, variant, store)] = qty

        previews = []

        for idx, (original_idx, row) in enumerate(df_filtered.iterrows()):
            product = row[self.config.product_name_column]
            variant = row.get(self.config.variant_column, "")
            product_name = str(product) if pd.notna(product) else ""

            excel_row = header_row + 3 + original_idx

            # Get product-specific store priority
            product_stores, uses_fallback = self._get_product_priority(product_name, available_stores)

            preview = TransferPreview(
                row_index=excel_row,
                product_name=product_name,
                variant=str(variant) if pd.notna(variant) else "",
                uses_fallback_priority=uses_fallback and self.sales_data is not None,
            )

            # Get product info for minimum sizes rule
            prod_info = product_data.get(product_name, {"rows": [], "total_sizes": 1})
            total_product_sizes = prod_info["total_sizes"]
            product_rows = prod_info["rows"]

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
                    partner_store = self._find_store_by_code(partner_code, product_stores)

                    if (partner_store and
                            partner_store not in self.config.excluded_stores):

                        decision_key = (product_name, partner_store)

                        # Check if we already evaluated this product/partner combination
                        if decision_key not in partner_transfer_decisions:
                            # Evaluate minimum sizes rule for this product/partner
                            partner_sizes_count = count_sizes_with_stock(product_rows, partner_store)

                            if should_apply_min_sizes_rule(partner_sizes_count, total_product_sizes):
                                # Count how many sizes sender can transfer
                                # (sizes where sender has excess AND partner has 0)
                                transferable_sizes = 0
                                for row_info in product_rows:
                                    sender_qty_row = row_info["store_quantities"].get(sender_store, 0)
                                    partner_qty_row = row_info["store_quantities"].get(partner_store, 0)
                                    if sender_qty_row > self.config.balance_threshold and partner_qty_row == 0:
                                        transferable_sizes += 1

                                # Can only transfer if 3+ sizes available
                                partner_transfer_decisions[decision_key] = (
                                    transferable_sizes >= MIN_SIZES_TO_ADD
                                )
                            else:
                                # Min sizes rule doesn't apply, allow normal transfer
                                partner_transfer_decisions[decision_key] = True

                        can_transfer = partner_transfer_decisions[decision_key]

                        if can_transfer:
                            # Check if partner needs this specific variant
                            variant_str = str(variant) if pd.notna(variant) else ""
                            partner_qty = working_inventory.get(
                                (product_name, variant_str, partner_store), 0
                            )

                            if partner_qty == 0 and remaining_excess > 0:
                                preview.transfers.append(Transfer(
                                    sender=sender_code,
                                    receiver=partner_store,
                                    quantity=1
                                ))
                                working_inventory[(product_name, variant_str, partner_store)] = 1
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
