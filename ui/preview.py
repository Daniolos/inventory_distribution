"""Preview rendering UI components.

This module provides Streamlit components for rendering distribution previews.
"""

import streamlit as st
import pandas as pd
import io
from datetime import datetime

from core.models import TransferPreview


def generate_problems_excel(previews: list[TransferPreview]) -> tuple[bytes, int]:
    """Generate Excel with problem cases from previews.
    
    Args:
        previews: List of transfer previews
        
    Returns:
        Tuple of (excel_bytes, problem_count)
    """
    problems = []
    
    for p in previews:
        if not p.has_transfers:
            continue
            
        # Fallback priority (product not in sales data)
        if p.uses_fallback_priority:
            problems.append({
                "Строка": p.row_index,
                "Артикул": p.product_name,
                "Вариант": p.variant or "—",
                "Проблема": "📊 Fallback",
                "Магазин": "—",
                "Детали": "Товар не найден в данных продаж",
            })
        
        # Standard distribution (<4 sizes)
        if p.uses_standard_distribution:
            problems.append({
                "Строка": p.row_index,
                "Артикул": p.product_name,
                "Вариант": p.variant or "—",
                "Проблема": "ℹ️ Standard",
                "Магазин": "—",
                "Детали": "<4 размеров — стандартное распределение",
            })
        
        # Skipped stores
        for skipped in p.skipped_stores:
            store_id = skipped.store_name.split()[0] if skipped.store_name else skipped.store_name
            
            if skipped.reason == "min_sizes":
                problems.append({
                    "Строка": p.row_index,
                    "Артикул": p.product_name,
                    "Вариант": p.variant or "—",
                    "Проблема": "📉 Min-Sizes",
                    "Магазин": store_id,
                    "Детали": "Недостаточно размеров для этого магазина",
                })
            elif skipped.reason == "excluded":
                problems.append({
                    "Строка": p.row_index,
                    "Артикул": p.product_name,
                    "Вариант": p.variant or "—",
                    "Проблема": "🚫 Excluded",
                    "Магазин": store_id,
                    "Детали": "Магазин исключён из распределения",
                })
    
    if not problems:
        return b"", 0
    
    df = pd.DataFrame(problems)
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, sheet_name="Проблемы")
    return excel_buffer.getvalue(), len(problems)


def render_preview(previews: list[TransferPreview], prefix: str = "default"):
    """Render the preview section with per-row status icons.

    Args:
        previews: List of transfer previews to display
        prefix: Unique prefix for widget keys to avoid duplicate IDs
    """
    # Calculate all counts
    total_rows = len(previews)
    rows_with_transfers = sum(1 for p in previews if p.has_transfers)
    total_transfers = sum(len(p.transfers) for p in previews)
    total_quantity = sum(p.total_quantity for p in previews)
    
    # Indicator counts (for rows with transfers only)
    fallback_count = sum(1 for p in previews if p.uses_fallback_priority and p.has_transfers)
    min_sizes_count = sum(1 for p in previews if p.min_sizes_skipped and p.has_transfers)
    standard_count = sum(1 for p in previews if p.uses_standard_distribution and p.has_transfers)
    excluded_count = sum(1 for p in previews if any(s.reason == "excluded" for s in p.skipped_stores) and p.has_transfers)

    # Basic metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего строк", total_rows)
    col2.metric("Строк с перемещениями", rows_with_transfers)
    col3.metric("Перемещения", total_transfers)
    col4.metric("Всего единиц", total_quantity)

    # Filter options
    show_only_transfers = st.checkbox(
        "Показать только строки с перемещениями",
        value=True,
        key=f"{prefix}_show_only_transfers"
    )
    
    # Indicator filter row (compact checkboxes) - whitelist: check to show ONLY these
    st.caption("Фильтр по индикаторам (✓ = показать только эти):")
    icol1, icol2, icol3, icol4, icol5 = st.columns(5)
    only_fallback = icol1.checkbox(f"📊 Fallback ({fallback_count})", value=False, key=f"{prefix}_filter_fallback")
    only_min_sizes = icol2.checkbox(f"📉 Min-Sizes ({min_sizes_count})", value=False, key=f"{prefix}_filter_min_sizes")
    only_standard = icol3.checkbox(f"ℹ️ Standard ({standard_count})", value=False, key=f"{prefix}_filter_standard")
    only_excluded = icol4.checkbox(f"🚫 Excluded ({excluded_count})", value=False, key=f"{prefix}_filter_excluded")
    
    # Problems download button
    problems_excel, problem_count = generate_problems_excel(previews)
    if problem_count > 0:
        icol5.download_button(
            label=f"📋 ({problem_count})",
            data=problems_excel,
            file_name=f"problems_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{prefix}_download_problems",
        )
    
    # Check if any filter is active
    any_filter_active = only_fallback or only_min_sizes or only_standard or only_excluded

    # Display previews
    displayed = 0
    for preview in previews:
        if show_only_transfers and not preview.has_transfers:
            continue
        
        # Apply indicator filters (whitelist: show ONLY rows matching checked indicators)
        has_excluded = any(s.reason == "excluded" for s in preview.skipped_stores)
        if any_filter_active:
            matches_filter = (
                (only_fallback and preview.uses_fallback_priority) or
                (only_min_sizes and preview.min_sizes_skipped) or
                (only_standard and preview.uses_standard_distribution) or
                (only_excluded and has_excluded)
            )
            if not matches_filter:
                continue

        displayed += 1
        variant_text = f" / {preview.variant}" if preview.variant else ""

        # Build multiple icons for header (all applicable icons shown)
        icons = []
        if preview.min_sizes_skipped:
            icons.append("📉")  # Min-sizes skip
        if preview.uses_fallback_priority:
            icons.append("📊")  # Fallback priority
        if preview.uses_standard_distribution:
            icons.append("ℹ️")  # Standard distribution (<4 sizes)
        row_icons = " ".join(icons)
        if row_icons:
            row_icons += " "

        if preview.has_transfers:
            header = f"{row_icons}Строка {preview.row_index}: {preview.product_name}{variant_text} ({len(preview.transfers)} перемещений)"
            with st.expander(header.strip(), expanded=False):
                # Show status reasons if applicable (using st.info for better visibility)
                if preview.uses_fallback_priority:
                    st.info("📊 Товар не найден в данных продаж — используется статический приоритет")
                if preview.uses_standard_distribution:
                    st.info("ℹ️ <4 размеров — стандартное распределение")
                
                # Show skipped stores before transfers (gray styling to distinguish from actual transfers)
                for skipped in preview.skipped_stores:
                    store_id = skipped.store_name.split()[0] if skipped.store_name else skipped.store_name
                    if skipped.reason == "min_sizes":
                        st.markdown(f'<span style="color: gray">└─ 📉 {store_id} пропущен (недостаточно размеров)</span>', unsafe_allow_html=True)
                    elif skipped.reason == "has_stock":
                        st.markdown(f'<span style="color: gray">└─ {store_id} пропущен (уже есть: {skipped.existing_qty} шт.)</span>', unsafe_allow_html=True)
                    elif skipped.reason == "excluded":
                        st.markdown(f'<span style="color: gray">└─ 🚫 {store_id} пропущен (исключён)</span>', unsafe_allow_html=True)
                
                # Show transfers (prominent styling)
                for transfer in preview.transfers:
                    receiver_display = transfer.receiver.split()[0] if transfer.receiver != "Сток" else "Сток"
                    st.markdown(f"└─ **{transfer.sender}** → **{receiver_display}**: {transfer.quantity} шт.")
        else:
            # No transfers - show reason
            if preview.skip_reason:
                st.markdown(
                    f"⚠️ **Строка {preview.row_index}:** {preview.product_name}{variant_text} "
                    f"— *{preview.skip_reason}*"
                )
            else:
                st.markdown(
                    f"**Строка {preview.row_index}:** {preview.product_name}{variant_text} "
                    f"— *(нет распределения)*"
                )

    if displayed == 0:
        st.info("Нет перемещений для текущих настроек.")
