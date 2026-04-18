"""Stock distribution logic - distributes from Stock/Photo Stock to stores.

Algorithm overview
------------------
Each run distributes inventory from a single source (Сток or Фото склад) to stores.

A product participates in the run only if its total number of sizes falls within the
configured range ``[min_product_sizes, max_product_sizes]``.

For every participating product, distribution happens in up to three phases. Phases
iterate stores in priority order, and each phase is completed for every store before
the next phase begins (fair distribution).

    Phase 1 — Reach the size-count target
        For each store: if current_filled_sizes + transferable_sizes >= target_sizes_filled,
        transfer 1 unit for each transferable size. Otherwise skip the store entirely
        (all-or-nothing, reason=target_not_reached).

    Phase 2 — Top up to 2 units per filled size (only if units_per_size >= 2)
        For each store: for every size currently at 1 unit, transfer +1 if stock left.

    Phase 3 — Top up to 3 units per filled size (only if units_per_size >= 3)
        For each store: for every size currently at 2 units, transfer +1 if stock left.
"""

import pandas as pd
from datetime import datetime
from typing import Optional, BinaryIO
from collections import defaultdict

from .models import (
    Transfer,
    TransferPreview,
    TransferResult,
    DistributionConfig,
    SalesPriorityData,
    SkippedStore,
    UpdatedInventoryResult,
    build_store_id_map,
    get_stock_value,
)
from .sales_parser import extract_product_code_from_input
from .config import OUTPUT_COLUMNS


class StockDistributor:
    """Distributes inventory from Сток/Фото склад to stores using a phased algorithm."""

    def __init__(
        self,
        config: DistributionConfig,
        sales_data: Optional[SalesPriorityData] = None
    ):
        self.config = config
        self.sales_data = sales_data
        self._store_id_map = build_store_id_map(config.store_priority)

    def _get_product_priority(
        self,
        product_name: str,
        available_stores: list[str]
    ) -> tuple[list[str], bool, list[str]]:
        """
        Get store priority for a specific product.

        Returns:
            (active_priority, uses_fallback, full_priority_with_excluded)
        """
        full_priority = [s for s in self.config.store_priority if s in available_stores]
        fallback_priority = [s for s in self.config.active_stores if s in available_stores]

        if not self.sales_data:
            return fallback_priority, False, full_priority

        product_code = extract_product_code_from_input(product_name)
        if not product_code:
            return fallback_priority, True, full_priority

        priority, found = self.sales_data.get_product_priority(
            product_code,
            self.config.store_priority,
            self._store_id_map
        )

        if not found:
            return fallback_priority, True, full_priority

        active_priority = [s for s in priority if s in available_stores and s in self.config.active_stores]
        full_priority_sales = [s for s in priority if s in available_stores]

        for store in fallback_priority:
            if store not in active_priority:
                active_priority.append(store)

        for store in full_priority:
            if store not in full_priority_sales:
                full_priority_sales.append(store)

        return active_priority, False, full_priority_sales

    def _get_source_column(self, source: str) -> str:
        if source == "photo":
            return self.config.photo_stock_column
        return self.config.stock_column

    def _get_source_name(self, source: str) -> str:
        return "Фото" if source == "photo" else "Сток"

    def _analyze_product_inventory(
        self,
        df: pd.DataFrame,
        source_column: str,
        available_stores: list[str],
        header_row: int = 0
    ) -> dict:
        """Group rows by product. Each product has a list of size-rows with stock data.

        Rows with an empty Характеристика are treated as product-level summary/total
        rows and skipped — distributing from them would double-count stock.
        """
        product_data: dict = defaultdict(lambda: {"rows": []})

        for original_idx, row in df.iterrows():
            product = row[self.config.product_name_column]
            if pd.isna(product) or product == "":
                continue

            variant_raw = row.get(self.config.variant_column, "")
            variant = str(variant_raw).strip() if pd.notna(variant_raw) else ""
            if variant == "":
                continue

            product = str(product)
            source_qty = get_stock_value(row.get(source_column, 0))

            store_quantities = {s: get_stock_value(row.get(s, 0)) for s in available_stores}
            excel_row = header_row + 3 + original_idx

            product_data[product]["rows"].append({
                "row_idx": excel_row,
                "variant": variant,
                "source_qty": source_qty,
                "store_quantities": store_quantities,
                "original_idx": original_idx,
            })

        return product_data

    def preview(self, df: pd.DataFrame, source: str = "stock", header_row: int = 0) -> list[TransferPreview]:
        """Generate preview of planned transfers without executing."""
        source_column = self._get_source_column(source)
        source_name = self._get_source_name(source)

        df_filtered = df[df[self.config.product_name_column].notna()].copy()
        df_filtered = df_filtered[df_filtered[self.config.product_name_column] != ""]

        available_stores = [s for s in self.config.store_priority if s in df_filtered.columns]
        product_data = self._analyze_product_inventory(df_filtered, source_column, available_stores, header_row)

        # Working state: per-row remaining stock and live store quantities
        remaining_stock: dict[int, int] = {}
        current_store_qty: dict[int, dict[str, int]] = {}
        for data in product_data.values():
            for row_data in data["rows"]:
                idx = row_data["original_idx"]
                remaining_stock[idx] = row_data["source_qty"]
                current_store_qty[idx] = dict(row_data["store_quantities"])

        previews_dict: dict[int, TransferPreview] = {}
        products_using_fallback: set[str] = set()
        products_filtered_out: set[str] = set()
        skipped_stores_per_row: dict[int, list[SkippedStore]] = defaultdict(list)
        target_not_reached_rows: set[int] = set()

        excluded_stores = set(self.config.excluded_stores)
        target = self.config.target_sizes_filled
        units = self.config.units_per_size
        size_min = self.config.min_product_sizes
        size_max = self.config.max_product_sizes

        def get_or_create_preview(row_data: dict, product_name: str) -> TransferPreview:
            idx = row_data["original_idx"]
            if idx not in previews_dict:
                previews_dict[idx] = TransferPreview(
                    row_index=row_data["row_idx"],
                    product_name=product_name,
                    variant=row_data["variant"],
                )
            return previews_dict[idx]

        def count_filled_sizes(product_rows: list[dict], store: str) -> int:
            return sum(1 for r in product_rows if current_store_qty[r["original_idx"]].get(store, 0) > 0)

        for product, data in product_data.items():
            rows = data["rows"]
            total_sizes = len(rows)

            # Range filter on product size count
            if total_sizes < size_min or total_sizes > size_max:
                products_filtered_out.add(product)
                continue

            active_priority, uses_fallback, full_priority = self._get_product_priority(product, available_stores)
            if uses_fallback and self.sales_data:
                products_using_fallback.add(product)

            # Track excluded stores (in priority order, for transparency)
            for store in full_priority:
                if store in excluded_stores:
                    for row_data in rows:
                        idx = row_data["original_idx"]
                        if current_store_qty[idx].get(store, 0) == 0:
                            skipped_stores_per_row[idx].append(SkippedStore(
                                store_name=store, reason="excluded", existing_qty=0
                            ))

            # ===== Phase 1: Reach size-count target =====
            for store in active_priority:
                if store in excluded_stores:
                    continue

                current_filled = count_filled_sizes(rows, store)
                if current_filled >= target:
                    continue  # Target already met — Phase 1 does nothing

                transferable = [
                    r for r in rows
                    if current_store_qty[r["original_idx"]].get(store, 0) == 0
                    and remaining_stock[r["original_idx"]] > 0
                ]

                if current_filled + len(transferable) < target:
                    # All-or-nothing: skip store
                    for row_data in rows:
                        idx = row_data["original_idx"]
                        if current_store_qty[idx].get(store, 0) == 0:
                            skipped_stores_per_row[idx].append(SkippedStore(
                                store_name=store, reason="target_not_reached", existing_qty=0
                            ))
                            target_not_reached_rows.add(idx)
                    continue

                # Eligible — transfer 1 unit to each transferable size
                for row_data in transferable:
                    idx = row_data["original_idx"]
                    preview = get_or_create_preview(row_data, product)
                    preview.transfers.append(Transfer(
                        sender=source_name, receiver=store, quantity=1
                    ))
                    remaining_stock[idx] -= 1
                    current_store_qty[idx][store] = current_store_qty[idx].get(store, 0) + 1

            # ===== Phase 2: Top up to 2 units per size =====
            if units >= 2:
                for store in active_priority:
                    if store in excluded_stores:
                        continue
                    for row_data in rows:
                        idx = row_data["original_idx"]
                        if current_store_qty[idx].get(store, 0) == 1 and remaining_stock[idx] > 0:
                            preview = get_or_create_preview(row_data, product)
                            preview.transfers.append(Transfer(
                                sender=source_name, receiver=store, quantity=1
                            ))
                            remaining_stock[idx] -= 1
                            current_store_qty[idx][store] += 1

            # ===== Phase 3: Top up to 3 units per size =====
            if units >= 3:
                for store in active_priority:
                    if store in excluded_stores:
                        continue
                    for row_data in rows:
                        idx = row_data["original_idx"]
                        if current_store_qty[idx].get(store, 0) == 2 and remaining_stock[idx] > 0:
                            preview = get_or_create_preview(row_data, product)
                            preview.transfers.append(Transfer(
                                sender=source_name, receiver=store, quantity=1
                            ))
                            remaining_stock[idx] -= 1
                            current_store_qty[idx][store] += 1

        # Create empty previews for rows without transfers
        for product, data in product_data.items():
            for row_data in data["rows"]:
                idx = row_data["original_idx"]
                if idx not in previews_dict:
                    previews_dict[idx] = TransferPreview(
                        row_index=row_data["row_idx"],
                        product_name=product,
                        variant=row_data["variant"],
                    )

        # Set per-row status flags
        for idx, preview in previews_dict.items():
            if preview.product_name in products_using_fallback:
                preview.uses_fallback_priority = True
            if idx in target_not_reached_rows:
                preview.target_not_reached = True
            if idx in skipped_stores_per_row:
                preview.skipped_stores = skipped_stores_per_row[idx]
            if preview.product_name in products_filtered_out:
                preview.skip_reason = (
                    f"Товар не в диапазоне размеров ({size_min}–{size_max})"
                )

        return sorted(previews_dict.values(), key=lambda p: p.row_index)

    def execute(self, df: pd.DataFrame, source: str = "stock", header_row: int = 0) -> list[TransferResult]:
        """Execute distribution and return transfer results grouped by receiver."""
        source_name = self._get_source_name(source)
        previews = self.preview(df, source, header_row)

        transfers_grouped: dict[tuple[str, str], list[tuple[str, str, int]]] = {}
        for preview in previews:
            for transfer in preview.transfers:
                key = (transfer.sender, transfer.receiver)
                transfers_grouped.setdefault(key, []).append((
                    preview.product_name, preview.variant, transfer.quantity
                ))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = []

        for (sender, receiver), items in transfers_grouped.items():
            receiver_code = receiver.split()[0] if receiver != source_name else "Сток"

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
                sender=sender, receiver=receiver_code, filename=filename, data=output_df
            ))

        return results

    def generate_updated_inventory(
        self,
        original_file: BinaryIO,
        df: pd.DataFrame,
        source: str = "stock",
        header_row: int = 0
    ) -> UpdatedInventoryResult:
        """Generate updated inventory Excel with stock decrements and store additions applied."""
        from .inventory_updater import generate_updated_inventory_result

        previews = self.preview(df, source, header_row)
        source_column = self._get_source_column(source)
        source_name = self._get_source_name(source)

        return generate_updated_inventory_result(
            original_file, previews, source_column, source_name, header_row
        )
