"""Stock distribution logic - distributes from Stock/Photo Stock to stores."""

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
)
from .sales_parser import extract_product_code_from_input
from .config import OUTPUT_COLUMNS

# Minimum sizes rule configuration
MIN_SIZES_THRESHOLD = 2  # If store has <= this many sizes, apply min sizes rule
MIN_SIZES_TO_ADD = 3     # Number of different sizes to add when rule applies


def get_stock_value(val) -> int:
    """Convert cell value to integer, treating NaN/empty as 0."""
    if pd.isna(val) or val == "" or val == "Остаток на складе":
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


class StockDistributor:
    """
    Distributes inventory from Stock (Сток) or Photo Stock (Фото склад) to stores.

    Distribution rules:
    - If store has 0-1 sizes of a product: add ALL available sizes (only if 3+ sizes available in stock)
    - If store has 2+ sizes of a product: normal distribution (1 item per variant with 0 stock)
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

    def _get_source_column(self, source: str) -> str:
        """Get the column name for the source."""
        if source == "photo":
            return self.config.photo_stock_column
        return self.config.stock_column

    def _get_source_name(self, source: str) -> str:
        """Get display name for the source."""
        return "Фото" if source == "photo" else "Сток"

    def _analyze_product_inventory(
        self,
        df: pd.DataFrame,
        source_column: str,
        active_stores: list[str],
        header_row: int = 0
    ) -> dict:
        """
        Analyze inventory by product to understand size distribution.

        Args:
            header_row: 0-indexed header row in Excel (used to calculate Excel row numbers)

        Returns:
            Dict with product name as key, containing:
            - rows: list of (row_idx, variant, source_qty, store_quantities)
            - sizes_in_stock: list of variants with source_qty > 0
        """
        product_data = defaultdict(lambda: {"rows": [], "sizes_in_stock": []})

        for idx, (original_idx, row) in enumerate(df.iterrows()):
            product = row[self.config.product_name_column]
            if pd.isna(product) or product == "":
                continue

            product = str(product)
            variant = str(row.get(self.config.variant_column, "")) if pd.notna(row.get(self.config.variant_column)) else ""
            source_qty = get_stock_value(row.get(source_column, 0))

            # Get store quantities for this row
            store_quantities = {}
            for store in active_stores:
                store_quantities[store] = get_stock_value(row.get(store, 0))

            # Calculate Excel row: header_row (0-based) + 2 (1 for 1-based, 1 for data after header) + original_idx
            # Using original_idx (pandas index) instead of idx to preserve correct row number after filtering
            excel_row = header_row + 2 + original_idx

            product_data[product]["rows"].append({
                "row_idx": excel_row,  # Excel row number for display
                "variant": variant,
                "source_qty": source_qty,
                "store_quantities": store_quantities,
                "original_idx": original_idx,
            })

            if source_qty > 0:
                product_data[product]["sizes_in_stock"].append(variant)

        return product_data

    def _get_store_sizes_count(self, product_rows: list, store: str) -> int:
        """Count how many different sizes a store has for a product (qty > 0)."""
        sizes_with_stock = set()
        for row_data in product_rows:
            if row_data["store_quantities"].get(store, 0) > 0:
                sizes_with_stock.add(row_data["variant"])
        return len(sizes_with_stock)

    def preview(self, df: pd.DataFrame, source: str = "stock", header_row: int = 0) -> list[TransferPreview]:
        """
        Generate preview of distributions without executing.

        Args:
            df: Input DataFrame (already loaded with correct header row)
            source: "stock" for Сток, "photo" for Фото склад
            header_row: 0-indexed header row in Excel (for displaying correct Excel row numbers)

        Returns:
            List of TransferPreview objects showing planned distributions
        """
        source_column = self._get_source_column(source)
        source_name = self._get_source_name(source)

        # Filter valid rows
        df_filtered = df[df[self.config.product_name_column].notna()].copy()
        df_filtered = df_filtered[df_filtered[self.config.product_name_column] != ""]

        # Get all stores that exist in the DataFrame (for analysis)
        available_stores = [
            s for s in self.config.store_priority
            if s in df_filtered.columns
        ]

        # Analyze inventory by product (using all available stores for quantity tracking)
        product_data = self._analyze_product_inventory(df_filtered, source_column, available_stores, header_row)

        # Track remaining stock per row (to avoid double-allocation)
        remaining_stock = {}
        for product, data in product_data.items():
            for row_data in data["rows"]:
                remaining_stock[row_data["original_idx"]] = row_data["source_qty"]

        # Create previews for all rows
        previews_dict = {}

        # Track which products have <4 sizes for per-row status
        products_under_4_sizes = set()
        # Track rows skipped due to min-sizes rule: {original_idx: skip_reason}
        skipped_rows_reasons = {}
        # Track products using fallback priority (not found in sales data)
        products_using_fallback = set()

        for product, data in product_data.items():
            sizes_in_stock = data["sizes_in_stock"]
            available_sizes_count = len(sizes_in_stock)
            total_product_sizes = len(data["rows"])  # All sizes of this product

            # Track products with <4 sizes (for per-row status)
            if total_product_sizes < 4:
                products_under_4_sizes.add(product)

            # Get product-specific store priority
            product_stores, uses_fallback = self._get_product_priority(product, available_stores)
            if uses_fallback and self.sales_data:
                products_using_fallback.add(product)

            for store in product_stores:
                store_sizes_count = self._get_store_sizes_count(data["rows"], store)

                # Determine which rule to apply
                # Minimum sizes rule only applies if:
                # 1. Store has <= 1 sizes of this product
                # 2. Product has at least 4 sizes total (otherwise use normal distribution)
                if store_sizes_count <= 1 and total_product_sizes >= 4:
                    # Rule: Need 3 different sizes, "all or nothing"
                    if available_sizes_count < MIN_SIZES_TO_ADD:
                        # Not enough sizes in stock, skip this product/store
                        # Mark rows with skip reason
                        for row_data in data["rows"]:
                            if row_data["store_quantities"].get(store, 0) == 0:
                                if row_data["original_idx"] not in skipped_rows_reasons:
                                    skipped_rows_reasons[row_data["original_idx"]] = f"Недостаточно размеров (есть {available_sizes_count}, нужно ≥3)"
                        continue

                    # Find rows with stock that store doesn't have
                    transferable_rows = []
                    for row_data in data["rows"]:
                        if row_data["source_qty"] > 0 and row_data["store_quantities"].get(store, 0) == 0:
                            if remaining_stock[row_data["original_idx"]] > 0:
                                transferable_rows.append(row_data)

                    # Need at least 3 different sizes to transfer
                    if len(transferable_rows) >= MIN_SIZES_TO_ADD:
                        # Transfer ALL sizes (minimum 3 required, checked above)
                        for row_data in transferable_rows:
                            if remaining_stock[row_data["original_idx"]] > 0:
                                # Create or get preview for this row
                                if row_data["original_idx"] not in previews_dict:
                                    previews_dict[row_data["original_idx"]] = TransferPreview(
                                        row_index=row_data["row_idx"],
                                        product_name=product,
                                        variant=row_data["variant"],
                                    )

                                previews_dict[row_data["original_idx"]].transfers.append(Transfer(
                                    sender=source_name,
                                    receiver=store,
                                    quantity=1
                                ))
                                remaining_stock[row_data["original_idx"]] -= 1

                else:
                    # Rule: Normal distribution - 1 item per variant with 0 stock
                    for row_data in data["rows"]:
                        if (row_data["store_quantities"].get(store, 0) == 0 and
                            remaining_stock[row_data["original_idx"]] > 0):

                            # Create or get preview for this row
                            if row_data["original_idx"] not in previews_dict:
                                previews_dict[row_data["original_idx"]] = TransferPreview(
                                    row_index=row_data["row_idx"],
                                    product_name=product,
                                    variant=row_data["variant"],
                                )

                            previews_dict[row_data["original_idx"]].transfers.append(Transfer(
                                sender=source_name,
                                receiver=store,
                                quantity=1
                            ))
                            remaining_stock[row_data["original_idx"]] -= 1

        # Create previews for rows without transfers
        for product, data in product_data.items():
            for row_data in data["rows"]:
                if row_data["original_idx"] not in previews_dict:
                    previews_dict[row_data["original_idx"]] = TransferPreview(
                        row_index=row_data["row_idx"],
                        product_name=product,
                        variant=row_data["variant"],
                    )

        # Set per-row status fields
        for original_idx, preview in previews_dict.items():
            # Check if this row was skipped due to min-sizes rule
            if original_idx in skipped_rows_reasons:
                preview.skip_reason = skipped_rows_reasons[original_idx]

            # Check if this product has <4 sizes (uses standard distribution)
            if preview.product_name in products_under_4_sizes:
                preview.uses_standard_distribution = True

            # Check if this product uses fallback priority (not found in sales data)
            if preview.product_name in products_using_fallback:
                preview.uses_fallback_priority = True

        # Sort by row index and return
        previews = sorted(previews_dict.values(), key=lambda p: p.row_index)
        return previews

    def execute(self, df: pd.DataFrame, source: str = "stock", header_row: int = 0) -> list[TransferResult]:
        """
        Execute distribution and return transfer results.

        Args:
            df: Input DataFrame (already loaded with correct header row)
            source: "stock" for Сток, "photo" for Фото склад
            header_row: 0-indexed header row in Excel

        Returns:
            List of TransferResult objects ready for download
        """
        source_name = self._get_source_name(source)

        # Get preview (contains all transfers)
        previews = self.preview(df, source, header_row)

        # Group transfers by (sender, receiver)
        transfers_grouped: dict[tuple[str, str], list[tuple[str, str, int]]] = {}

        for preview in previews:
            for transfer in preview.transfers:
                key = (transfer.sender, transfer.receiver)
                if key not in transfers_grouped:
                    transfers_grouped[key] = []
                transfers_grouped[key].append((
                    preview.product_name,
                    preview.variant,
                    transfer.quantity
                ))

        # Create results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = []

        for (sender, receiver), items in transfers_grouped.items():
            # Extract store code from name (e.g., "125007 MSK-PC-..." -> "125007")
            receiver_code = receiver.split()[0] if receiver != source_name else "Сток"

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

            filename = f"{source_name}_to_{receiver_code}_{timestamp}.xlsx"

            results.append(TransferResult(
                sender=sender,
                receiver=receiver_code,
                filename=filename,
                data=output_df
            ))

        return results
