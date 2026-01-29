"""Data models for inventory distribution."""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class Transfer:
    """Represents a single transfer between sender and receiver."""
    sender: str
    receiver: str
    quantity: int


@dataclass
class TransferPreview:
    """Preview of transfers for a single product row."""
    row_index: int
    product_name: str
    variant: str
    transfers: list[Transfer] = field(default_factory=list)
    
    # Per-row status indicators
    skip_reason: Optional[str] = None  # e.g., "min_sizes_not_met"
    uses_standard_distribution: bool = False  # Product has <4 sizes

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
