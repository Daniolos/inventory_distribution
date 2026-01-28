"""Stock distribution logic - distributes from Stock/Photo Stock to stores."""

import pandas as pd
from datetime import datetime
from typing import Optional

from .models import Transfer, TransferPreview, TransferResult, DistributionConfig
from .config import OUTPUT_COLUMNS


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

    For each row:
    - Takes items from source (Stock or Photo Stock)
    - Distributes 1 item to each store that has 0 inventory
    - Follows priority order, respects exclusions
    """

    def __init__(self, config: DistributionConfig):
        self.config = config

    def _get_source_column(self, source: str) -> str:
        """Get the column name for the source."""
        if source == "photo":
            return self.config.photo_stock_column
        return self.config.stock_column

    def _get_source_name(self, source: str) -> str:
        """Get display name for the source."""
        return "Фото" if source == "photo" else "Сток"

    def preview(self, df: pd.DataFrame, source: str = "stock") -> list[TransferPreview]:
        """
        Generate preview of distributions without executing.

        Args:
            df: Input DataFrame (already loaded with correct header row)
            source: "stock" for Сток, "photo" for Фото склад

        Returns:
            List of TransferPreview objects showing planned distributions
        """
        source_column = self._get_source_column(source)
        source_name = self._get_source_name(source)

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
            source_qty = get_stock_value(row.get(source_column, 0))

            preview = TransferPreview(
                row_index=idx + 1,  # 1-based for display
                product_name=str(product) if pd.notna(product) else "",
                variant=str(variant) if pd.notna(variant) else "",
            )

            if source_qty <= 0:
                previews.append(preview)
                continue

            remaining = source_qty

            for store in active_stores:
                if remaining <= 0:
                    break

                store_qty = get_stock_value(row.get(store, 0))

                # Only distribute to stores with 0 inventory
                if store_qty == 0:
                    preview.transfers.append(Transfer(
                        sender=source_name,
                        receiver=store,
                        quantity=1
                    ))
                    remaining -= 1

            previews.append(preview)

        return previews

    def execute(self, df: pd.DataFrame, source: str = "stock") -> list[TransferResult]:
        """
        Execute distribution and return transfer results.

        Args:
            df: Input DataFrame (already loaded with correct header row)
            source: "stock" for Сток, "photo" for Фото склад

        Returns:
            List of TransferResult objects ready for download
        """
        source_name = self._get_source_name(source)

        # Get preview (contains all transfers)
        previews = self.preview(df, source)

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
