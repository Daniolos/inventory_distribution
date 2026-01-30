"""Results rendering UI components.

This module provides Streamlit components for rendering transfer results and downloads.
"""

import streamlit as st
import io
import zipfile
from datetime import datetime

from core.models import TransferResult


def render_results(results: list[TransferResult]):
    """Render the download section with ZIP and individual file downloads.
    
    Args:
        results: List of transfer results to render
    """
    st.success(f"{len(results)} файлов перемещений создано!")

    # Summary
    total_items = sum(r.item_count for r in results)
    st.metric("Всего записей", total_items)

    # ZIP download
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for result in results:
            excel_buffer = io.BytesIO()
            result.data.to_excel(excel_buffer, index=False)
            zip_file.writestr(result.filename, excel_buffer.getvalue())

    st.download_button(
        label="Скачать всё в ZIP",
        data=zip_buffer.getvalue(),
        file_name=f"transfers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip",
        type="primary",
    )

    st.divider()
    st.subheader("Отдельные файлы")

    for result in results:
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.markdown(f"**{result.filename}**")
        col2.write(f"{result.item_count} записей")

        excel_buffer = io.BytesIO()
        result.data.to_excel(excel_buffer, index=False)

        col3.download_button(
            label="Скачать",
            data=excel_buffer.getvalue(),
            file_name=result.filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{result.filename}",
        )
