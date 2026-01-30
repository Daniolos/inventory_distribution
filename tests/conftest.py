"""Shared fixtures for inventory distribution tests."""

import pytest
import pandas as pd
from core.models import DistributionConfig

# Store columns used in tests (subset for simplicity)
STORE_COLS = [
    "125007 MSK-PC-Гагаринский",
    "125008 MSK-PC-РИО Ленинский",
    "129877 MSK-PC-Мега 1 Теплый Стан",
    "130143 MSK-PCM-Мега 2 Химки",
    "150002 MSK-DV-Капитолий",
]


@pytest.fixture
def config():
    """Standard DistributionConfig for tests."""
    return DistributionConfig(
        store_priority=STORE_COLS,
        excluded_stores=[],
        balance_threshold=2,
    )


@pytest.fixture
def base_columns():
    """Base columns required for all DataFrames."""
    return [
        "Номенклатура",
        "Характеристика",
        "Коллекция (сезон)",
        "Наименование_доп",
    ]


def create_test_row(
    product: str,
    variant: str,
    stock: int = 0,
    photo_stock: int = 0,
    store_quantities: dict = None,
) -> dict:
    """Helper to create a test row with all required columns."""
    row = {
        "Номенклатура": product,
        "Характеристика": variant,
        "Коллекция (сезон)": "2024",
        "Наименование_доп": "Test",
        "Сток": stock,
        "Фото склад": photo_stock,
    }
    # Set all stores to 0 by default
    for store in STORE_COLS:
        row[store] = 0
    # Override with provided quantities
    if store_quantities:
        for store, qty in store_quantities.items():
            row[store] = qty
    return row


def create_test_df(rows: list[dict], header_row: int = 7) -> pd.DataFrame:
    """Create a test DataFrame from a list of row dicts.

    Args:
        rows: List of row dictionaries
        header_row: The header row number (unused, kept for compatibility)

    Returns:
        DataFrame with default pandas index starting from 0
        (matches real pd.read_excel behavior with skiprows)
    """
    df = pd.DataFrame(rows)
    # Keep default pandas index (0, 1, 2, ...) to match real pd.read_excel behavior
    # The distributor calculates Excel rows as: header_row + 3 + original_idx
    return df
