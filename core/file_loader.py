"""Excel file loading utilities.

This module provides functions for loading Excel files with automatic header detection.
It is UI-agnostic and can be used by both Streamlit and CLI applications.
"""

import pandas as pd
from typing import BinaryIO

from .config import PRODUCT_NAME_COLUMN


def find_header_row(file: BinaryIO, max_rows: int = 20) -> tuple[int | None, str | None]:
    """Automatically find the header row by searching for the product name column.

    Args:
        file: File-like object (uploaded file or opened file)
        max_rows: Maximum rows to search

    Returns:
        Tuple of (header_row_index, error_message)
        If found: (row_index, None)
        If not found: (None, error_message)
    """
    try:
        # Read first max_rows without header
        preview_df = pd.read_excel(file, header=None, nrows=max_rows)

        # Search for the row containing the product name column
        for idx, row in preview_df.iterrows():
            row_values = [str(v) for v in row.values if pd.notna(v)]
            if PRODUCT_NAME_COLUMN in row_values:
                # Reset file pointer for subsequent reads
                file.seek(0)
                return int(idx), None

        # Not found
        file.seek(0)
        return None, f"Строка заголовка с '{PRODUCT_NAME_COLUMN}' не найдена в первых {max_rows} строках"

    except Exception as e:
        file.seek(0)
        return None, f"Ошибка чтения файла: {e}"


def load_excel_with_header(
    file: BinaryIO,
    max_header_search_rows: int = 20
) -> tuple[pd.DataFrame | None, int | None, str | None]:
    """Load Excel file with automatic header detection.

    This function:
    1. Finds the header row by searching for PRODUCT_NAME_COLUMN
    2. Loads the Excel with that header row
    3. Skips the sub-header row (contains "Остаток на складе")

    Args:
        file: File-like object (uploaded file or opened file)
        max_header_search_rows: Maximum rows to search for header

    Returns:
        Tuple of (DataFrame, header_row_index, error_message)
        If successful: (df, header_row, None)
        If error: (None, None, error_message)
    """
    header_row, error = find_header_row(file, max_header_search_rows)
    
    if error:
        return None, None, error
    
    try:
        # Skip the sub-header row (contains "Остаток на складе") right after header
        df = pd.read_excel(file, header=header_row, skiprows=[header_row + 1])
        file.seek(0)
        return df, header_row, None
    except Exception as e:
        file.seek(0)
        return None, None, f"Ошибка чтения файла: {e}"


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: list[str]
) -> tuple[bool, list[str]]:
    """Validate that DataFrame has all required columns.

    Args:
        df: DataFrame to validate
        required_columns: List of required column names

    Returns:
        Tuple of (is_valid, list_of_missing_columns)
    """
    missing = [col for col in required_columns if col not in df.columns]
    return len(missing) == 0, missing
