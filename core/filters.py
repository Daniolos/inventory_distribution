"""Data filtering utilities.

This module provides functions for filtering DataFrame rows based on various criteria.
It is UI-agnostic and can be used by both Streamlit and CLI applications.
"""

import pandas as pd

from .config import (
    PRODUCT_NAME_COLUMN,
    COLLECTION_COLUMN,
    ADDITIONAL_NAME_COLUMN,
)


def format_filter_value(val) -> str:
    """Format a value for display in filter options.

    Converts floats that are whole numbers to integers (e.g., 2221.0 -> "2221").
    
    Args:
        val: Value to format
        
    Returns:
        Formatted string representation
    """
    if pd.isna(val):
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


def extract_article_name(nomenclature) -> str:
    """Extract article name from Номенклатура.

    Example: 'Мужские шорты_C3 34770.4007/6214' -> 'Мужские шорты'
    
    Args:
        nomenclature: Value from Номенклатура column
        
    Returns:
        Article name (part before underscore)
    """
    if pd.isna(nomenclature):
        return ""
    # Split on '_' and take first part (the name before the code)
    parts = str(nomenclature).split('_')
    return parts[0].strip()


def get_unique_article_types(df: pd.DataFrame) -> list[str]:
    """Extract unique article types from DataFrame.

    Args:
        df: DataFrame with PRODUCT_NAME_COLUMN
        
    Returns:
        Sorted list of unique article types (non-empty)
    """
    if PRODUCT_NAME_COLUMN not in df.columns:
        return []
    
    article_types = df[PRODUCT_NAME_COLUMN].apply(extract_article_name).unique().tolist()
    article_types = [v for v in article_types if v.strip()]
    article_types.sort()
    return article_types


def get_unique_collections(df: pd.DataFrame) -> list[str]:
    """Extract unique collections from DataFrame.

    Args:
        df: DataFrame with COLLECTION_COLUMN
        
    Returns:
        Sorted list of unique collections (non-empty)
    """
    if COLLECTION_COLUMN not in df.columns:
        return []
    
    collections = df[COLLECTION_COLUMN].dropna().unique().tolist()
    collections = [format_filter_value(v) for v in collections]
    collections = [v for v in collections if v.strip()]
    collections.sort()
    return collections


def get_unique_additional_names(df: pd.DataFrame) -> list[str]:
    """Extract unique additional names from DataFrame.

    Args:
        df: DataFrame with ADDITIONAL_NAME_COLUMN
        
    Returns:
        Sorted list of unique additional names (non-empty)
    """
    if ADDITIONAL_NAME_COLUMN not in df.columns:
        return []
    
    names = df[ADDITIONAL_NAME_COLUMN].dropna().unique().tolist()
    names = [format_filter_value(v) for v in names]
    names = [v for v in names if v.strip()]
    names.sort()
    return names


def apply_article_type_filter(
    df: pd.DataFrame,
    selected_types: list[str]
) -> pd.DataFrame:
    """Filter DataFrame by article types.

    Args:
        df: Input DataFrame
        selected_types: List of article types to include
        
    Returns:
        Filtered DataFrame
    """
    if not selected_types:
        return df
    
    # Get all unique types to check if all are selected
    all_types = set(get_unique_article_types(df))
    
    if set(selected_types) == all_types:
        # All types selected - no filtering needed
        return df
    
    return df[df[PRODUCT_NAME_COLUMN].apply(extract_article_name).isin(selected_types)]


def apply_collection_filter(
    df: pd.DataFrame,
    selected_collections: list[str]
) -> pd.DataFrame:
    """Filter DataFrame by collections.

    Args:
        df: Input DataFrame
        selected_collections: List of collections to include
        
    Returns:
        Filtered DataFrame
    """
    if not selected_collections or COLLECTION_COLUMN not in df.columns:
        return df
    
    return df[df[COLLECTION_COLUMN].apply(format_filter_value).isin(selected_collections)]


def apply_additional_name_filter(
    df: pd.DataFrame,
    selected_names: list[str]
) -> pd.DataFrame:
    """Filter DataFrame by additional names.

    Args:
        df: Input DataFrame
        selected_names: List of additional names to include
        
    Returns:
        Filtered DataFrame
    """
    if not selected_names or ADDITIONAL_NAME_COLUMN not in df.columns:
        return df
    
    return df[df[ADDITIONAL_NAME_COLUMN].apply(format_filter_value).isin(selected_names)]


def apply_all_filters(
    df: pd.DataFrame,
    article_types: list[str] | None = None,
    collections: list[str] | None = None,
    additional_names: list[str] | None = None
) -> pd.DataFrame:
    """Apply all filters to DataFrame.

    Args:
        df: Input DataFrame
        article_types: Optional list of article types to include
        collections: Optional list of collections to include
        additional_names: Optional list of additional names to include
        
    Returns:
        Filtered DataFrame
    """
    result = df
    
    if article_types:
        result = apply_article_type_filter(result, article_types)
    
    if collections:
        result = apply_collection_filter(result, collections)
    
    if additional_names:
        result = apply_additional_name_filter(result, additional_names)
    
    return result
