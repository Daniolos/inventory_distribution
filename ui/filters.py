"""Filter UI components for Streamlit.

This module provides Streamlit UI components for filtering DataFrames.
It uses core.filters for the underlying filter logic.
"""

import streamlit as st
import pandas as pd

from core.config import (
    PRODUCT_NAME_COLUMN,
    COLLECTION_COLUMN,
    ADDITIONAL_NAME_COLUMN,
    ARTICLE_TYPE_FILTER_LABEL,
)
from core.filters import (
    extract_article_name,
    format_filter_value,
    get_unique_article_types,
    get_unique_collections,
    get_unique_additional_names,
)


def render_article_type_filter(
    df: pd.DataFrame,
    prefix: str,
) -> list[str]:
    """Render article type filter as checkbox expander with form.
    
    Uses st.form to prevent reruns during checkbox selection.
    
    Args:
        df: Input DataFrame
        prefix: Unique prefix for widget keys
        
    Returns:
        List of selected article types
    """
    # Extract unique article types
    article_types = get_unique_article_types(df)
    
    if not article_types:
        return []
    
    total_count = len(article_types)
    
    # Session state keys
    result_key = f"{prefix}_article_filter_result"
    select_all_key = f"{prefix}_article_select_all"
    clear_all_key = f"{prefix}_article_clear_all"
    expander_key = f"{prefix}_article_expander_open"
    
    # Initialize session state
    if result_key not in st.session_state:
        st.session_state[result_key] = set()
    if expander_key not in st.session_state:
        st.session_state[expander_key] = False
    
    # Handle button flags from previous run
    if st.session_state.get(select_all_key, False):
        for at in article_types:
            st.session_state[f"{prefix}_cb_{at}"] = True
        st.session_state[select_all_key] = False
        st.session_state[expander_key] = True  # Keep expander open
    
    if st.session_state.get(clear_all_key, False):
        for at in article_types:
            st.session_state[f"{prefix}_cb_{at}"] = False
        st.session_state[clear_all_key] = False
        st.session_state[expander_key] = True  # Keep expander open
    
    selected_count = len(st.session_state[result_key])
    
    # Expander with count in label (persisted state)
    with st.expander(
        f"Фильтр по {ARTICLE_TYPE_FILTER_LABEL} ({selected_count} из {total_count})",
        expanded=st.session_state[expander_key]
    ):
        
        # Action buttons
        col_btn1, col_btn2, _ = st.columns([1, 1, 4])
        
        with col_btn1:
            if st.button("Выбрать все", key=f"{prefix}_btn_select_all"):
                st.session_state[select_all_key] = True
                st.rerun()
        
        with col_btn2:
            if st.button("Очистить", key=f"{prefix}_btn_clear"):
                st.session_state[clear_all_key] = True
                st.rerun()
        
        # Form prevents rerun on checkbox clicks
        with st.form(key=f"{prefix}_article_filter_form"):
            # Two-column layout for checkboxes
            col1, col2 = st.columns(2)
            
            for i, article_type in enumerate(article_types):
                checkbox_key = f"{prefix}_cb_{article_type}"
                
                # Initialize checkbox state from applied result
                if checkbox_key not in st.session_state:
                    st.session_state[checkbox_key] = article_type in st.session_state[result_key]
                
                col = col1 if i % 2 == 0 else col2
                with col:
                    st.checkbox(article_type, key=checkbox_key)
            
            # Submit button
            submitted = st.form_submit_button("Применить фильтр")
            
            if submitted:
                # Collect all checked items and update result
                selected = set()
                for at in article_types:
                    if st.session_state.get(f"{prefix}_cb_{at}", False):
                        selected.add(at)
                st.session_state[result_key] = selected
                st.session_state[expander_key] = True  # Keep expander open
                st.rerun()  # Rerun to update counter in label
    
    return list(st.session_state[result_key])


def render_filters(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Render filter UI and return filtered DataFrame.

    Args:
        df: Input DataFrame
        prefix: Unique prefix for widget keys

    Returns:
        Filtered DataFrame
    """
    # Check which filter columns are available
    has_collection = COLLECTION_COLUMN in df.columns
    has_additional_name = ADDITIONAL_NAME_COLUMN in df.columns
    has_nomenclature = PRODUCT_NAME_COLUMN in df.columns

    if not has_collection and not has_additional_name and not has_nomenclature:
        return df

    filtered_df = df.copy()

    # 1. Article type filter FIRST (checkbox expander)
    if has_nomenclature:
        # Get all unique article types for comparison
        all_article_types = set(get_unique_article_types(df))
        selected_types = render_article_type_filter(df, prefix)
        if selected_types:
            # If all types are selected, include rows with empty article type too
            if set(selected_types) == all_article_types:
                # No filtering needed - all types selected
                pass
            else:
                filtered_df = filtered_df[
                    filtered_df[PRODUCT_NAME_COLUMN].apply(extract_article_name).isin(selected_types)
                ]

    # 2. Collection filter (multiselect)
    if has_collection:
        unique_collections = get_unique_collections(df)

        if unique_collections:
            selected_collections = st.multiselect(
                f"Фильтр по {COLLECTION_COLUMN}",
                options=unique_collections,
                default=[],
                key=f"{prefix}_filter_collection",
                placeholder="Выберите...",
                help="Оставьте пустым, чтобы включить всё"
            )
            if selected_collections:
                filtered_df = filtered_df[
                    filtered_df[COLLECTION_COLUMN].apply(format_filter_value).isin(selected_collections)
                ]

    # 3. Additional name filter (multiselect)
    if has_additional_name:
        unique_names = get_unique_additional_names(df)

        if unique_names:
            selected_names = st.multiselect(
                f"Фильтр по {ADDITIONAL_NAME_COLUMN}",
                options=unique_names,
                default=[],
                key=f"{prefix}_filter_additional_name",
                placeholder="Выберите...",
                help="Оставьте пустым, чтобы включить всё"
            )
            if selected_names:
                filtered_df = filtered_df[
                    filtered_df[ADDITIONAL_NAME_COLUMN].apply(format_filter_value).isin(selected_names)
                ]

    # Show filter summary
    if len(filtered_df) != len(df):
        st.info(f"Отфильтровано: {len(filtered_df)} из {len(df)} строк")

    return filtered_df
