"""Preview rendering UI components."""

import streamlit as st
import pandas as pd
import io
from datetime import datetime

from core.models import TransferPreview


def generate_problems_excel(previews: list[TransferPreview]) -> tuple[bytes, int]:
    """Generate Excel with problem cases from previews.

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
                "Проблема": "📊 Нет в продажах",
                "Магазин": "—",
                "Детали": "Товар не найден в данных продаж",
            })

        # Skipped stores
        for skipped in p.skipped_stores:
            store_id = skipped.store_name.split()[0] if skipped.store_name else skipped.store_name

            if skipped.reason == "target_not_reached":
                problems.append({
                    "Строка": p.row_index,
                    "Артикул": p.product_name,
                    "Вариант": p.variant or "—",
                    "Проблема": "📉 Цель не достигнута",
                    "Магазин": store_id,
                    "Детали": "Недостаточно размеров для достижения цели",
                })
            elif skipped.reason == "excluded":
                problems.append({
                    "Строка": p.row_index,
                    "Артикул": p.product_name,
                    "Вариант": p.variant or "—",
                    "Проблема": "🚫 Исключённые",
                    "Магазин": store_id,
                    "Детали": "Магазин исключён из распределения",
                })

    if not problems:
        return b"", 0

    df = pd.DataFrame(problems)
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, sheet_name="Замечания")
    return excel_buffer.getvalue(), len(problems)


def render_preview(previews: list[TransferPreview], prefix: str = "default"):
    """Render the preview section with per-row status icons."""
    total_rows = len(previews)
    rows_with_transfers = sum(1 for p in previews if p.has_transfers)
    total_transfers = sum(len(p.transfers) for p in previews)
    total_quantity = sum(p.total_quantity for p in previews)

    # Indicator counts
    fallback_count = sum(1 for p in previews if p.uses_fallback_priority and p.has_transfers)
    target_not_reached_count = sum(1 for p in previews if p.target_not_reached)
    excluded_count = sum(1 for p in previews if any(s.reason == "excluded" for s in p.skipped_stores))
    filtered_count = sum(1 for p in previews if p.skip_reason and not p.has_transfers)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего строк", total_rows)
    col2.metric("Строк с перемещениями", rows_with_transfers)
    col3.metric("Перемещения", total_transfers)
    col4.metric("Всего единиц", total_quantity)

    # Indicator filter row
    st.caption("Фильтр по индикаторам (✓ = показать только эти):")
    icol1, icol2, icol3, icol4 = st.columns(4)
    only_fallback = icol1.checkbox(
        f"📊 Нет в продажах ({fallback_count})",
        value=False,
        key=f"{prefix}_filter_fallback",
        help="Товар не найден в данных продаж — используется статический приоритет"
    )
    only_target_not_reached = icol2.checkbox(
        f"📉 Цель не достигнута ({target_not_reached_count})",
        value=False,
        key=f"{prefix}_filter_target",
        help="Магазин пропущен, т.к. невозможно достигнуть целевое количество размеров"
    )
    only_excluded = icol3.checkbox(
        f"🚫 Исключённые ({excluded_count})",
        value=False,
        key=f"{prefix}_filter_excluded",
        help="Магазин исключён из распределения"
    )
    only_filtered = icol4.checkbox(
        f"🔢 Вне фильтра ({filtered_count})",
        value=False,
        key=f"{prefix}_filter_filtered",
        help="Товар не попал в диапазон размеров"
    )

    # Remarks download button
    remarks_excel, remark_count = generate_problems_excel(previews)
    if remark_count > 0:
        st.download_button(
            label=f"Скачать замечания ({remark_count})",
            data=remarks_excel,
            file_name=f"remarks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{prefix}_download_remarks",
            type="primary",
            use_container_width=True,
        )

    show_only_transfers = st.checkbox(
        "Показать только строки с перемещениями",
        value=True,
        key=f"{prefix}_show_only_transfers"
    )

    any_filter_active = only_fallback or only_target_not_reached or only_excluded or only_filtered

    displayed = 0
    for preview in previews:
        if show_only_transfers and not preview.has_transfers:
            continue

        has_excluded = any(s.reason == "excluded" for s in preview.skipped_stores)
        is_filtered_out = preview.skip_reason is not None and not preview.has_transfers
        if any_filter_active:
            matches_filter = (
                (only_fallback and preview.uses_fallback_priority) or
                (only_target_not_reached and preview.target_not_reached) or
                (only_excluded and has_excluded) or
                (only_filtered and is_filtered_out)
            )
            if not matches_filter:
                continue

        displayed += 1
        variant_text = f" / {preview.variant}" if preview.variant else ""

        icons = []
        if preview.target_not_reached:
            icons.append("📉")
        if preview.uses_fallback_priority:
            icons.append("📊")
        if has_excluded:
            icons.append("🚫")
        if is_filtered_out:
            icons.append("🔢")
        row_icons = " ".join(icons)
        if row_icons:
            row_icons += " "

        if preview.has_transfers:
            header = f"{row_icons}Строка {preview.row_index}: {preview.product_name}{variant_text} ({len(preview.transfers)} перемещений)"
            with st.expander(header.strip(), expanded=False):
                if preview.uses_fallback_priority:
                    st.info("📊 Товар не найден в данных продаж — используется статический приоритет")

                for skipped in preview.skipped_stores:
                    store_id = skipped.store_name.split()[0] if skipped.store_name else skipped.store_name
                    if skipped.reason == "target_not_reached":
                        st.markdown(f'<span style="color: gray">└─ 📉 {store_id} пропущен (цель по размерам не достигается)</span>', unsafe_allow_html=True)
                    elif skipped.reason == "has_stock":
                        st.markdown(f'<span style="color: gray">└─ {store_id} пропущен (уже есть: {skipped.existing_qty} шт.)</span>', unsafe_allow_html=True)
                    elif skipped.reason == "excluded":
                        st.markdown(f'<span style="color: gray">└─ 🚫 {store_id} пропущен (исключён)</span>', unsafe_allow_html=True)

                for transfer in preview.transfers:
                    receiver_display = transfer.receiver.split()[0] if transfer.receiver != "Сток" else "Сток"
                    st.markdown(f"└─ **{transfer.sender}** → **{receiver_display}**: {transfer.quantity} шт.")
        else:
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
