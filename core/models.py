"""Data models for inventory distribution."""

from dataclasses import dataclass, field
from typing import Optional
import re
import pandas as pd


def extract_store_id(store_name: str) -> Optional[int]:
    """
    Extract numeric store ID from store name.
    Handles leading zeros. Only matches valid store format.

    Valid format: 5-7 digit ID followed by space and store name
    Example: "0130143 MSK-PCM-Мега 2 Химки" -> 130143
    Example: "125007 MSK-PC-Гагаринский" -> 125007

    Returns None for non-store rows like headers or totals.
    """
    if not store_name:
        return None
    # Match store format: 5-7 digits (with optional leading zeros) followed by space and name
    match = re.match(r"^0*(\d{5,7})\s+\S", str(store_name))
    if match:
        return int(match.group(1))
    return None


def build_store_id_map(store_names: list[str]) -> dict[int, str]:
    """
    Build mapping from store ID to full store name.

    Args:
        store_names: List of store names (from config.store_priority)

    Returns:
        Dict mapping store_id (int) to full store name
    """
    result = {}
    for name in store_names:
        store_id = extract_store_id(name)
        if store_id:
            result[store_id] = name
    return result


@dataclass
class StoreSales:
    """Sales data for a single store for a specific product."""
    store_id: int          # Numeric ID (e.g., 130143)
    store_name: str        # Full name from sales file
    quantity: int          # Sales quantity


@dataclass
class ProductSalesData:
    """Sales data for a single product across all stores."""
    product_code: str      # e.g., "C5 21354.2110/1010"
    raw_name: str          # Original name from sales file
    total_quantity: int    # Total sales across all stores
    store_sales: list[StoreSales] = field(default_factory=list)

    def get_priority_order(
        self,
        fallback_priority: list[str],
        store_id_map: dict[int, str]
    ) -> list[str]:
        """
        Get store names ordered by sales (descending).
        Ties broken by fallback_priority order.

        Args:
            fallback_priority: User-configured static priority list
            store_id_map: Mapping from store_id (int) to full store name

        Returns:
            List of store names in priority order (highest sales first)
        """
        def sort_key(store_sale: StoreSales) -> tuple:
            # Get the canonical store name from our map
            store_name = store_id_map.get(store_sale.store_id, "")
            # Find position in fallback priority (for tiebreaker)
            fallback_idx = (
                fallback_priority.index(store_name)
                if store_name in fallback_priority
                else len(fallback_priority)
            )
            # Sort by: sales descending (-quantity), then fallback position ascending
            return (-store_sale.quantity, fallback_idx)

        sorted_sales = sorted(self.store_sales, key=sort_key)

        # Return store names from our canonical map
        result = []
        for s in sorted_sales:
            store_name = store_id_map.get(s.store_id)
            if store_name:
                result.append(store_name)
        return result


@dataclass
class SalesPriorityData:
    """Container for all sales priority data."""
    products: dict[str, ProductSalesData] = field(default_factory=dict)  # key = product_code

    def get_product_priority(
        self,
        product_code: str,
        fallback_priority: list[str],
        store_id_map: dict[int, str]
    ) -> tuple[list[str], bool]:
        """
        Get store priority for a specific product.

        Args:
            product_code: Extracted product code
            fallback_priority: User-configured static priority
            store_id_map: Mapping from store_id to full store name

        Returns:
            Tuple of (priority_list, was_found_in_sales_data)
            - If found: (sales-based priority, True)
            - If not found: (fallback_priority, False)
        """
        if product_code in self.products:
            priority = self.products[product_code].get_priority_order(
                fallback_priority, store_id_map
            )
            # If sales data exists but resulted in empty list, use fallback
            if priority:
                return priority, True
        return fallback_priority, False


@dataclass
class Transfer:
    """Represents a single transfer between sender and receiver."""
    sender: str
    receiver: str
    quantity: int


@dataclass
class SkippedStore:
    """Represents a store that was skipped during distribution."""
    store_name: str      # Full store name (e.g., "125007 MSK-PC-Гагаринский")
    reason: str          # "has_stock" or "min_sizes"
    existing_qty: int = 0  # Number of existing pieces (for has_stock reason)


@dataclass
class TransferPreview:
    """Preview of transfers for a single product row."""
    row_index: int
    product_name: str
    variant: str
    transfers: list[Transfer] = field(default_factory=list)
    
    # Skipped stores tracking
    skipped_stores: list[SkippedStore] = field(default_factory=list)
    
    # Per-row status indicators
    skip_reason: Optional[str] = None  # e.g., "min_sizes_not_met"
    uses_standard_distribution: bool = False  # Product has <4 sizes
    uses_fallback_priority: bool = False  # Product not found in sales data
    min_sizes_skipped: bool = False  # Store was skipped due to min-sizes rule

    @property
    def total_quantity(self) -> int:
        """Total quantity being transferred for this product."""
        return sum(t.quantity for t in self.transfers)

    @property
    def has_transfers(self) -> bool:
        """Whether this row has any transfers."""
        return len(self.transfers) > 0
    
    @property
    def has_warning(self) -> bool:
        """Whether this row has a warning status."""
        return self.skip_reason is not None
    
    @property
    def has_info(self) -> bool:
        """Whether this row has an info status."""
        return self.uses_standard_distribution

    @property
    def has_fallback_priority(self) -> bool:
        """Whether this row uses fallback priority (not found in sales data)."""
        return self.uses_fallback_priority





@dataclass
class TransferResult:
    """Result containing transfer data for export."""
    sender: str
    receiver: str
    filename: str
    data: pd.DataFrame

    @property
    def item_count(self) -> int:
        """Number of items in this transfer."""
        return len(self.data)


@dataclass
class UpdatedInventoryResult:
    """Result containing updated inventory Excel data."""
    filename: str
    data: bytes  # Excel file bytes
    source_column: str  # "Сток" or "Фото склад"
    total_rows_updated: int
    total_quantity_transferred: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class DistributionConfig:
    """Configuration for distribution operations."""
    store_priority: list[str] = field(default_factory=list)
    excluded_stores: list[str] = field(default_factory=list)
    balance_threshold: int = 2

    # Column names
    stock_column: str = "Сток"
    photo_stock_column: str = "Фото склад"
    product_name_column: str = "Номенклатура"
    variant_column: str = "Характеристика"

    @property
    def active_stores(self) -> list[str]:
        """Get stores that are not excluded."""
        return [s for s in self.store_priority if s not in self.excluded_stores]

    def to_dict(self) -> dict:
        """Convert config to dictionary for JSON export."""
        return {
            "store_priority": self.store_priority,
            "excluded_stores": self.excluded_stores,
            "balance_threshold": self.balance_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DistributionConfig":
        """Create config from dictionary (JSON import)."""
        return cls(
            store_priority=data.get("store_priority", []),
            excluded_stores=data.get("excluded_stores", []),
            balance_threshold=data.get("balance_threshold", 2),
        )
