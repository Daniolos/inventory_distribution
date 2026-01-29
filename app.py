"""
Inventory Distribution Streamlit App

A user-friendly web interface for distributing inventory between stores.
"""

import streamlit as st
import pandas as pd
import io
import zipfile
from datetime import datetime

from core import (
    StockDistributor,
    InventoryBalancer,
    DistributionConfig,
    TransferPreview,
    TransferResult,
)
from core.config import (
    DEFAULT_STORE_PRIORITY,
    DEFAULT_EXCLUDED_STORES,
    DEFAULT_BALANCE_THRESHOLD,
    PRODUCT_NAME_COLUMN,
    VARIANT_COLUMN,
    STOCK_COLUMN,
    PHOTO_STOCK_COLUMN,
    COLLECTION_COLUMN,
    ADDITIONAL_NAME_COLUMN,
)

# Page config
st.set_page_config(
    page_title="Inventory Distribution",
    page_icon="📦",
    layout="wide",
)

# Initialize session state
if "store_priority" not in st.session_state:
    st.session_state.store_priority = DEFAULT_STORE_PRIORITY.copy()
if "excluded_stores" not in st.session_state:
    st.session_state.excluded_stores = DEFAULT_EXCLUDED_STORES.copy()
if "balance_threshold" not in st.session_state:
    st.session_state.balance_threshold = DEFAULT_BALANCE_THRESHOLD
# Separate session states for each tab to avoid duplicate widget IDs
if "preview_results_script1" not in st.session_state:
    st.session_state.preview_results_script1 = None
if "transfer_results_script1" not in st.session_state:
    st.session_state.transfer_results_script1 = None
if "preview_results_script2" not in st.session_state:
    st.session_state.preview_results_script2 = None
if "transfer_results_script2" not in st.session_state:
    st.session_state.transfer_results_script2 = None


def move_store_up(idx: int):
    """Move a store up in priority."""
    if idx > 0:
        stores = st.session_state.store_priority
        stores[idx], stores[idx - 1] = stores[idx - 1], stores[idx]
        st.session_state.store_priority = stores


def move_store_down(idx: int):
    """Move a store down in priority."""
    stores = st.session_state.store_priority
    if idx < len(stores) - 1:
        stores[idx], stores[idx + 1] = stores[idx + 1], stores[idx]
        st.session_state.store_priority = stores


def validate_file(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Validate that the uploaded file has required columns."""
    errors = []

    if PRODUCT_NAME_COLUMN not in df.columns:
        errors.append(f"Column '{PRODUCT_NAME_COLUMN}' not found")
    if VARIANT_COLUMN not in df.columns:
        errors.append(f"Column '{VARIANT_COLUMN}' not found")
    if STOCK_COLUMN not in df.columns:
        errors.append(f"Column '{STOCK_COLUMN}' not found")

    # Check for at least one store column
    store_columns = [
        col for col in df.columns
        if col in st.session_state.store_priority
    ]
    if not store_columns:
        errors.append("No known store columns found")

    return len(errors) == 0, errors


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

    if not has_collection and not has_additional_name:
        return df

    with st.expander("🔍 Filter Options", expanded=False):
        filtered_df = df.copy()

        if has_collection:
            # Get unique non-empty values
            unique_collections = df[COLLECTION_COLUMN].dropna().unique().tolist()
            unique_collections = [str(v) for v in unique_collections if str(v).strip()]
            unique_collections.sort()

            if unique_collections:
                selected_collections = st.multiselect(
                    f"Filter by {COLLECTION_COLUMN}",
                    options=unique_collections,
                    default=[],
                    key=f"{prefix}_filter_collection",
                    help="Leave empty to include all"
                )
                if selected_collections:
                    filtered_df = filtered_df[
                        filtered_df[COLLECTION_COLUMN].astype(str).isin(selected_collections)
                    ]

        if has_additional_name:
            unique_names = df[ADDITIONAL_NAME_COLUMN].dropna().unique().tolist()
            unique_names = [str(v) for v in unique_names if str(v).strip()]
            unique_names.sort()

            if unique_names:
                selected_names = st.multiselect(
                    f"Filter by {ADDITIONAL_NAME_COLUMN}",
                    options=unique_names,
                    default=[],
                    key=f"{prefix}_filter_additional_name",
                    help="Leave empty to include all"
                )
                if selected_names:
                    filtered_df = filtered_df[
                        filtered_df[ADDITIONAL_NAME_COLUMN].astype(str).isin(selected_names)
                    ]

        # Show filter summary
        if len(filtered_df) != len(df):
            st.info(f"Filtered: {len(filtered_df)} of {len(df)} rows")

    return filtered_df


def find_header_row(file, max_rows: int = 20) -> tuple[int | None, str | None]:
    """Automatically find the header row by searching for the product name column.

    Args:
        file: Uploaded file object
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
        return None, f"Header row with '{PRODUCT_NAME_COLUMN}' not found in first {max_rows} rows"

    except Exception as e:
        file.seek(0)
        return None, f"Error reading file: {e}"


def get_config() -> DistributionConfig:
    """Create config from current session state."""
    return DistributionConfig(
        store_priority=st.session_state.store_priority.copy(),
        excluded_stores=st.session_state.excluded_stores.copy(),
        balance_threshold=st.session_state.balance_threshold,
    )


def render_preview(previews: list[TransferPreview], prefix: str = "default"):
    """Render the preview section.

    Args:
        previews: List of transfer previews to display
        prefix: Unique prefix for widget keys to avoid duplicate IDs
    """
    # Summary
    total_rows = len(previews)
    rows_with_transfers = sum(1 for p in previews if p.has_transfers)
    total_transfers = sum(len(p.transfers) for p in previews)
    total_quantity = sum(p.total_quantity for p in previews)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Rows", total_rows)
    col2.metric("Rows with Transfers", rows_with_transfers)
    col3.metric("Transfers", total_transfers)
    col4.metric("Total Units", total_quantity)

    # Filter options
    show_only_transfers = st.checkbox(
        "Show only rows with transfers",
        value=True,
        key=f"{prefix}_show_only_transfers"
    )

    # Display previews
    displayed = 0
    for preview in previews:
        if show_only_transfers and not preview.has_transfers:
            continue

        displayed += 1
        variant_text = f" / {preview.variant}" if preview.variant else ""

        if preview.has_transfers:
            with st.expander(
                f"Row {preview.row_index}: {preview.product_name}{variant_text} "
                f"({len(preview.transfers)} Transfers)",
                expanded=False
            ):
                for transfer in preview.transfers:
                    receiver_display = transfer.receiver.split()[0] if transfer.receiver != "Сток" else "Сток"
                    st.markdown(f"  └─ **{transfer.sender}** → **{receiver_display}**: {transfer.quantity} items")
        else:
            st.markdown(
                f"**Row {preview.row_index}:** {preview.product_name}{variant_text} "
                f"— *(no distribution)*"
            )

    if displayed == 0:
        st.info("No transfers for the current settings.")


def render_results(results: list[TransferResult]):
    """Render the download section."""
    st.success(f"{len(results)} transfer files generated!")

    # Summary
    total_items = sum(r.item_count for r in results)
    st.metric("Total Entries", total_items)

    # ZIP download
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for result in results:
            excel_buffer = io.BytesIO()
            result.data.to_excel(excel_buffer, index=False)
            zip_file.writestr(result.filename, excel_buffer.getvalue())

    st.download_button(
        label="Download All as ZIP",
        data=zip_buffer.getvalue(),
        file_name=f"transfers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip",
        type="primary",
    )

    st.divider()
    st.subheader("Individual Files")

    for result in results:
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.markdown(f"**{result.filename}**")
        col2.write(f"{result.item_count} entries")

        excel_buffer = io.BytesIO()
        result.data.to_excel(excel_buffer, index=False)

        col3.download_button(
            label="Download",
            data=excel_buffer.getvalue(),
            file_name=result.filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{result.filename}",
        )


# Main UI
st.title("📦 Inventory Distribution")
st.markdown("Distribute inventory to stores")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")

    # Store priority editor
    st.subheader("Priority Order")
    st.caption("Stores at the top receive items first")

    for idx, store in enumerate(st.session_state.store_priority):
        col1, col2, col3, col4 = st.columns([1, 6, 1, 1])

        col1.write(f"**{idx + 1}.**")
        col2.write(store[:30] + "..." if len(store) > 30 else store)

        if idx > 0:
            col3.button("↑", key=f"up_{idx}", on_click=move_store_up, args=(idx,))
        else:
            col3.write("")

        if idx < len(st.session_state.store_priority) - 1:
            col4.button("↓", key=f"down_{idx}", on_click=move_store_down, args=(idx,))
        else:
            col4.write("")

    st.divider()

    # Exclusion editor
    st.subheader("Excluded Stores")
    st.caption("These stores receive no items")

    new_excluded = []
    for store in st.session_state.store_priority:
        is_excluded = store in st.session_state.excluded_stores
        if st.checkbox(store[:40], value=is_excluded, key=f"exclude_{store}"):
            new_excluded.append(store)
    st.session_state.excluded_stores = new_excluded

# Main content area
tab1, tab2 = st.tabs([
    "📤 Script 1: Stock → Stores",
    "⚖️ Script 2: Balance Inventory"
])

# Tab 1: Stock Distribution
with tab1:
    st.subheader("Distribute Stock to Stores")
    st.markdown("""
    Distributes inventory from **Сток** or **Фото склад** to stores with 0 inventory.
    Each store receives a maximum of 1 item per product.
    """)

    # Source selection
    source_option = st.radio(
        "Select source:",
        ["Сток (Stock)", "Фото склад (Photo Stock)"],
        horizontal=True,
    )
    source = "stock" if "Сток" in source_option else "photo"

    # File upload
    uploaded_file = st.file_uploader(
        "Upload Excel File",
        type=["xlsx"],
        key="file_script1",
    )

    if uploaded_file:
        try:
            # Auto-detect header row
            header_row, header_error = find_header_row(uploaded_file)
            if header_error:
                st.error(header_error)
                st.info(f"Tip: Ensure the Excel file has '{PRODUCT_NAME_COLUMN}' as a column header.")
            else:
                df = pd.read_excel(uploaded_file, header=header_row)
                st.success(f"File loaded: {len(df)} rows (header found in row {header_row + 1})")

                # Validate
                is_valid, errors = validate_file(df)
                if not is_valid:
                    for error in errors:
                        st.error(error)
                else:
                    # Apply filters
                    df_filtered = render_filters(df, prefix="script1")

                    # Preview button
                    col1, col2 = st.columns(2)

                    if col1.button("Generate Preview", key="preview_script1", type="secondary"):
                        config = get_config()
                        distributor = StockDistributor(config)

                        with st.spinner("Generating preview..."):
                            st.session_state.preview_results_script1 = distributor.preview(df_filtered, source)
                            st.session_state.transfer_results_script1 = None

                    if col2.button("Generate Transfers", key="execute_script1", type="primary"):
                        config = get_config()
                        distributor = StockDistributor(config)

                        with st.spinner("Generating transfers..."):
                            st.session_state.transfer_results_script1 = distributor.execute(df_filtered, source)

                    # Display results
                    if st.session_state.preview_results_script1 and not st.session_state.transfer_results_script1:
                        st.divider()
                        st.subheader("Preview")
                        render_preview(st.session_state.preview_results_script1, prefix="script1")

                    if st.session_state.transfer_results_script1:
                        st.divider()
                        st.subheader("Downloads")
                        render_results(st.session_state.transfer_results_script1)

        except Exception as e:
            st.error(f"Error loading file: {e}")

# Tab 2: Inventory Balancing
with tab2:
    st.subheader("Balance Inventory Between Stores")
    st.markdown("""
    Distributes surplus from stores with high inventory to empty stores.
    Remaining surplus goes back to **Сток**.
    """)

    # Threshold setting
    threshold = st.number_input(
        "Balance Threshold",
        min_value=1,
        max_value=10,
        value=st.session_state.balance_threshold,
        help="Stores with more than this value will be balanced",
    )
    st.session_state.balance_threshold = threshold

    # File upload
    uploaded_file2 = st.file_uploader(
        "Upload Excel File",
        type=["xlsx"],
        key="file_script2",
    )

    if uploaded_file2:
        try:
            # Auto-detect header row
            header_row, header_error = find_header_row(uploaded_file2)
            if header_error:
                st.error(header_error)
                st.info(f"Tip: Ensure the Excel file has '{PRODUCT_NAME_COLUMN}' as a column header.")
            else:
                df2 = pd.read_excel(uploaded_file2, header=header_row)
                st.success(f"File loaded: {len(df2)} rows (header found in row {header_row + 1})")

                # Validate
                is_valid, errors = validate_file(df2)
                if not is_valid:
                    for error in errors:
                        st.error(error)
                else:
                    # Apply filters
                    df2_filtered = render_filters(df2, prefix="script2")

                    # Preview button
                    col1, col2 = st.columns(2)

                    if col1.button("Generate Preview", key="preview_script2", type="secondary"):
                        config = get_config()
                        balancer = InventoryBalancer(config)

                        with st.spinner("Generating preview..."):
                            st.session_state.preview_results_script2 = balancer.preview(df2_filtered)
                            st.session_state.transfer_results_script2 = None

                    if col2.button("Generate Transfers", key="execute_script2", type="primary"):
                        config = get_config()
                        balancer = InventoryBalancer(config)

                        with st.spinner("Generating transfers..."):
                            st.session_state.transfer_results_script2 = balancer.execute(df2_filtered)

                    # Display results
                    if st.session_state.preview_results_script2 and not st.session_state.transfer_results_script2:
                        st.divider()
                        st.subheader("Preview")
                        render_preview(st.session_state.preview_results_script2, prefix="script2")

                    if st.session_state.transfer_results_script2:
                        st.divider()
                        st.subheader("Downloads")
                        render_results(st.session_state.transfer_results_script2)

        except Exception as e:
            st.error(f"Error loading file: {e}")

# Footer
st.divider()
st.caption("Inventory Distribution App v1.0")
