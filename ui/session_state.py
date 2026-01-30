"""Session state initialization and management.

This module provides functions for initializing and managing Streamlit session state.
"""

import streamlit as st

from core.config import (
    DEFAULT_STORE_PRIORITY,
    DEFAULT_EXCLUDED_STORES,
    DEFAULT_BALANCE_THRESHOLD,
)


def init_session_state():
    """Initialize all session state variables with defaults."""
    # Store configuration
    if "store_priority" not in st.session_state:
        st.session_state.store_priority = DEFAULT_STORE_PRIORITY.copy()
    if "excluded_stores" not in st.session_state:
        st.session_state.excluded_stores = DEFAULT_EXCLUDED_STORES.copy()
    if "balance_threshold" not in st.session_state:
        st.session_state.balance_threshold = DEFAULT_BALANCE_THRESHOLD
    
    # Preview/Results for Script 1 (Stock → Stores)
    if "preview_results_script1" not in st.session_state:
        st.session_state.preview_results_script1 = None
    if "transfer_results_script1" not in st.session_state:
        st.session_state.transfer_results_script1 = None
    if "updated_inventory_script1" not in st.session_state:
        st.session_state.updated_inventory_script1 = None
    
    # Preview/Results for Script 2 (Balance Inventory)
    if "preview_results_script2" not in st.session_state:
        st.session_state.preview_results_script2 = None
    if "transfer_results_script2" not in st.session_state:
        st.session_state.transfer_results_script2 = None
    
    # Sales priority data
    if "sales_priority_data" not in st.session_state:
        st.session_state.sales_priority_data = None
    if "sales_file_name" not in st.session_state:
        st.session_state.sales_file_name = None


def move_store_up(idx: int):
    """Move a store up in priority.
    
    Args:
        idx: Index of store to move up
    """
    if idx > 0:
        stores = st.session_state.store_priority
        stores[idx], stores[idx - 1] = stores[idx - 1], stores[idx]
        st.session_state.store_priority = stores


def move_store_down(idx: int):
    """Move a store down in priority.
    
    Args:
        idx: Index of store to move down
    """
    stores = st.session_state.store_priority
    if idx < len(stores) - 1:
        stores[idx], stores[idx + 1] = stores[idx + 1], stores[idx]
        st.session_state.store_priority = stores
