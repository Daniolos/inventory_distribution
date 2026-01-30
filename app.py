"""
Inventory Distribution Streamlit App

A user-friendly web interface for distributing inventory between stores.
"""

import streamlit as st
import pandas as pd

from core import (
    StockDistributor,
    InventoryBalancer,
    DistributionConfig,
    parse_sales_file,
    find_header_row,
)
from core.config import (
    PRODUCT_NAME_COLUMN,
    VARIANT_COLUMN,
    STOCK_COLUMN,
    PHOTO_STOCK_COLUMN,
    STORE_BALANCE_PAIRS,
)
from ui import (
    init_session_state,
    move_store_up,
    move_store_down,
    render_filters,
    render_preview,
    render_results,
)

# Page config
st.set_page_config(
    page_title="Распределение товаров",
    page_icon="📦",
    layout="wide",
)

# Initialize session state
init_session_state()


def validate_file(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Validate that the uploaded file has required columns.
    
    Args:
        df: Input DataFrame
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []
    required_cols = [PRODUCT_NAME_COLUMN, VARIANT_COLUMN]

    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Отсутствует столбец: '{col}'")

    # Check for at least one of: Stock or Photo Stock
    has_stock = STOCK_COLUMN in df.columns
    has_photo = PHOTO_STOCK_COLUMN in df.columns

    if not has_stock and not has_photo:
        errors.append(f"Отсутствуют столбцы '{STOCK_COLUMN}' и '{PHOTO_STOCK_COLUMN}'")

    return len(errors) == 0, errors


def get_config() -> DistributionConfig:
    """Create config from current session state.

    Returns:
        DistributionConfig with current settings
    """
    return DistributionConfig(
        store_priority=st.session_state.store_priority,
        excluded_stores=st.session_state.excluded_stores,
        balance_threshold=st.session_state.balance_threshold,
        store_balance_pairs=STORE_BALANCE_PAIRS,
    )


# Title
st.title("📦 Распределение товаров")
st.markdown("Распределение товаров по магазинам")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Настройки")

    # Sales priority upload (FIRST - most important)
    st.subheader("📊 Приоритет по продажам")
    st.caption("Приоритет магазинов определяется по количеству проданных единиц каждого товара")

    sales_file = st.file_uploader(
        "Загрузить файл продаж",
        type=["xlsx"],
        key="sales_priority_file",
        help="Excel с данными продаж по магазинам. Магазин с наибольшими продажами получает приоритет 1."
    )

    if sales_file:
        try:
            sales_data = parse_sales_file(sales_file)
            st.session_state.sales_priority_data = sales_data
            st.session_state.sales_file_name = sales_file.name

            # Show summary
            all_stores = set()
            for p in sales_data.products.values():
                for s in p.store_sales:
                    all_stores.add(s.store_id)
            st.success(f"Найдено {len(sales_data.products)} артикулов, {len(all_stores)} магазинов")

        except Exception as e:
            st.error(f"Ошибка разбора файла: {e}")
    else:
        # File removed (X clicked) - clear session state
        if st.session_state.sales_priority_data is not None:
            st.session_state.sales_priority_data = None
            st.session_state.sales_file_name = None

    # Show status when no file loaded
    if not st.session_state.sales_priority_data:
        st.caption("⚠️ Файл не загружен — используется статический приоритет (см. ниже)")

    st.divider()

    # Store priority editor (fallback/tiebreaker)
    st.subheader("Статический приоритет")
    st.caption("Используется как запасной вариант или при равных продажах")

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
    st.subheader("Исключённые магазины")
    st.caption("Эти магазины не получают товары")

    new_excluded = []
    for store in st.session_state.store_priority:
        is_excluded = store in st.session_state.excluded_stores
        if st.checkbox(store[:40], value=is_excluded, key=f"exclude_{store}"):
            new_excluded.append(store)
    st.session_state.excluded_stores = new_excluded

# Main content area
tab1, tab2 = st.tabs([
    "📤 Скрипт 1: Сток → Магазины",
    "⚖️ Скрипт 2: Балансировка остатков"
])

# Tab 1: Stock Distribution
with tab1:
    st.subheader("Распределение со Стока в Магазины")
    st.markdown("""
    Распределяет товары из **Стока** или **Фото склада** в магазины с нулевыми остатками.
    Каждый магазин получает максимум 1 единицу товара.
    """)

    # Source selection
    source_option = st.radio(
        "Выберите источник:",
        ["Сток", "Фото склад"],
        horizontal=True,
    )
    source = "stock" if "Сток" in source_option else "photo"

    # File upload
    uploaded_file = st.file_uploader(
        "Загрузить Excel файл",
        type=["xlsx"],
        key="file_script1",
    )

    if uploaded_file:
        try:
            # Auto-detect header row
            header_row, header_error = find_header_row(uploaded_file)
            if header_error:
                st.error(header_error)
                st.info(f"Совет: Убедитесь, что в Excel файле есть столбец '{PRODUCT_NAME_COLUMN}' в заголовке.")
            else:
                # Skip the sub-header row (contains "Остаток на складе") right after header
                df = pd.read_excel(uploaded_file, header=header_row, skiprows=[header_row + 1])
                st.success(f"Файл загружен: {len(df)} строк (заголовок найден в строке {header_row + 1})")

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

                    if col1.button("Предпросмотр", key="preview_script1", type="secondary"):
                        config = get_config()
                        distributor = StockDistributor(
                            config,
                            sales_data=st.session_state.sales_priority_data
                        )

                        with st.spinner("Генерация предпросмотра..."):
                            st.session_state.preview_results_script1 = distributor.preview(df_filtered, source, header_row)
                            st.session_state.transfer_results_script1 = None
                            st.session_state.updated_inventory_script1 = None

                    if col2.button("Создать перемещения", key="execute_script1", type="primary"):
                        config = get_config()
                        distributor = StockDistributor(
                            config,
                            sales_data=st.session_state.sales_priority_data
                        )

                        with st.spinner("Создание перемещений..."):
                            st.session_state.transfer_results_script1 = distributor.execute(df_filtered, source, header_row)

                            # Generate updated inventory Excel
                            uploaded_file.seek(0)  # Reset file pointer
                            st.session_state.updated_inventory_script1 = distributor.generate_updated_inventory(
                                uploaded_file,
                                df_filtered,
                                source,
                                header_row
                            )

                    # Display results
                    if st.session_state.preview_results_script1 and not st.session_state.transfer_results_script1:
                        st.divider()
                        st.subheader("Предпросмотр")
                        render_preview(
                            st.session_state.preview_results_script1, 
                            prefix="script1"
                        )

                    if st.session_state.transfer_results_script1:
                        st.divider()
                        st.subheader("Загрузки")
                        render_results(
                            st.session_state.transfer_results_script1,
                            updated_inventory=st.session_state.updated_inventory_script1
                        )

        except Exception as e:
            st.error(f"Ошибка загрузки файла: {e}")

# Tab 2: Inventory Balancing
with tab2:
    st.subheader("Балансировка остатков между магазинами")
    st.markdown("""
    Перемещает излишки (> порога) на **Сток**.

    **Исключение:** Пары магазинов могут балансировать между собой:
    - 125004 (EKT-Гринвич) ↔ 125005 (EKT-Мега)
    - 125008 (MSK-РИО Ленинский) ↔ 129877 (MSK-Мега Теплый Стан)

    Эти пары сначала передают 1 ед. партнёру (если у него 0), затем остаток идёт на Сток.
    """)

    # Threshold setting
    threshold = st.number_input(
        "Порог балансировки",
        min_value=1,
        max_value=10,
        value=st.session_state.balance_threshold,
        help="Магазины с количеством больше этого значения будут сбалансированы",
    )
    st.session_state.balance_threshold = threshold

    # File upload
    uploaded_file2 = st.file_uploader(
        "Загрузить Excel файл",
        type=["xlsx"],
        key="file_script2",
    )

    if uploaded_file2:
        try:
            # Auto-detect header row
            header_row, header_error = find_header_row(uploaded_file2)
            if header_error:
                st.error(header_error)
                st.info(f"Совет: Убедитесь, что в Excel файле есть столбец '{PRODUCT_NAME_COLUMN}' в заголовке.")
            else:
                # Skip the sub-header row (contains "Остаток на складе") right after header
                df2 = pd.read_excel(uploaded_file2, header=header_row, skiprows=[header_row + 1])
                st.success(f"Файл загружен: {len(df2)} строк (заголовок найден в строке {header_row + 1})")

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

                    if col1.button("Предпросмотр", key="preview_script2", type="secondary"):
                        config = get_config()
                        balancer = InventoryBalancer(
                            config,
                            sales_data=st.session_state.sales_priority_data
                        )

                        with st.spinner("Генерация предпросмотра..."):
                            st.session_state.preview_results_script2 = balancer.preview(df2_filtered, header_row)
                            st.session_state.transfer_results_script2 = None

                    if col2.button("Создать перемещения", key="execute_script2", type="primary"):
                        config = get_config()
                        balancer = InventoryBalancer(
                            config,
                            sales_data=st.session_state.sales_priority_data
                        )

                        with st.spinner("Создание перемещений..."):
                            st.session_state.transfer_results_script2 = balancer.execute(df2_filtered, header_row)

                    # Display results
                    if st.session_state.preview_results_script2 and not st.session_state.transfer_results_script2:
                        st.divider()
                        st.subheader("Предпросмотр")
                        render_preview(
                            st.session_state.preview_results_script2, 
                            prefix="script2"
                        )

                    if st.session_state.transfer_results_script2:
                        st.divider()
                        st.subheader("Загрузки")
                        render_results(st.session_state.transfer_results_script2)

        except Exception as e:
            st.error(f"Ошибка загрузки файла: {e}")

# Footer
st.divider()
st.caption("Приложение «Распределение товаров» v1.0")
