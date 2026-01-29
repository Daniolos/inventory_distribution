"""Tests for sales priority parser."""

import pytest
import pandas as pd
import io

from core.sales_parser import (
    extract_product_code_from_sales,
    extract_product_code_from_input,
    parse_sales_file,
)
from core.models import (
    extract_store_id,
    build_store_id_map,
    SalesPriorityData,
    ProductSalesData,
    StoreSales,
)


class TestExtractProductCode:
    """Tests for product code extraction functions."""

    def test_extract_from_sales_valid(self):
        """Test extracting product code from sales format."""
        # Format with underscore prefix (duplicated code)
        assert extract_product_code_from_sales("_C5 21354.2110/1010_C5 21354.2110/1010") == "C5 21354.2110/1010"
        assert extract_product_code_from_sales("_ABC123_ABC123") == "ABC123"

    def test_extract_from_sales_with_name_prefix(self):
        """Test extracting from format with product name prefix."""
        # Format: "Product Name_CODE" -> extract CODE after LAST underscore
        assert extract_product_code_from_sales("Джемпер V-образный ворот_C5 50706.5037/7015") == "C5 50706.5037/7015"
        assert extract_product_code_from_sales("Мужское поло короткий рукав_C5 20084.2004/2105") == "C5 20084.2004/2105"
        assert extract_product_code_from_sales("Simple Name_CODE123") == "CODE123"

    def test_extract_from_sales_store_row_returns_none(self):
        """Test that store rows (starting with digits) return None."""
        assert extract_product_code_from_sales("125007 MSK-PC-Гагаринский") is None
        assert extract_product_code_from_sales("0130143 MSK-PCM-Мега 2 Химки") is None

    def test_extract_from_sales_invalid(self):
        """Test invalid sales format returns None."""
        assert extract_product_code_from_sales("") is None
        assert extract_product_code_from_sales(None) is None
        assert extract_product_code_from_sales("No underscore") is None
        assert extract_product_code_from_sales("Номенклатура") is None  # Header row

    def test_extract_from_input_valid(self):
        """Test extracting product code from input file format."""
        assert extract_product_code_from_input("Мужское поло короткий рукав_C5 20084.2004/2105") == "C5 20084.2004/2105"
        assert extract_product_code_from_input("Product Name_CODE123") == "CODE123"

    def test_extract_from_input_invalid(self):
        """Test invalid input format returns None."""
        assert extract_product_code_from_input("") is None
        assert extract_product_code_from_input(None) is None
        assert extract_product_code_from_input("No underscore here") is None


class TestExtractStoreId:
    """Tests for store ID extraction."""

    def test_extract_with_leading_zero(self):
        """Test extracting store ID with leading zeros."""
        assert extract_store_id("0130143 MSK-PCM-Мега 2 Химки") == 130143

    def test_extract_without_leading_zero(self):
        """Test extracting store ID without leading zeros."""
        assert extract_store_id("125007 MSK-PC-Гагаринский") == 125007

    def test_extract_invalid(self):
        """Test invalid store format returns None."""
        assert extract_store_id("") is None
        assert extract_store_id(None) is None
        assert extract_store_id("_C5 21354.2110/1010_") is None

    def test_extract_rejects_non_store_rows(self):
        """Test that header/metadata rows are not matched as stores."""
        # Too few digits
        assert extract_store_id("123 Something") is None
        assert extract_store_id("1234 Something") is None
        # No space after digits
        assert extract_store_id("125007") is None
        # Header rows from Excel
        assert extract_store_id("Итого") is None
        assert extract_store_id("Номенклатура") is None
        assert extract_store_id("Склад") is None


class TestBuildStoreIdMap:
    """Tests for building store ID map."""

    def test_build_map(self):
        """Test building store ID to name mapping."""
        store_names = [
            "125007 MSK-PC-Гагаринский",
            "130143 MSK-PCM-Мега 2 Химки",
            "125006 KZN-PC-Мега",
        ]
        result = build_store_id_map(store_names)

        assert result[125007] == "125007 MSK-PC-Гагаринский"
        assert result[130143] == "130143 MSK-PCM-Мега 2 Химки"
        assert result[125006] == "125006 KZN-PC-Мега"


class TestProductSalesData:
    """Tests for ProductSalesData priority ordering."""

    def test_get_priority_order_by_sales(self):
        """Test that stores are ordered by sales (descending)."""
        product = ProductSalesData(
            product_code="C5 21354",
            raw_name="_C5 21354_C5 21354",
            total_quantity=100,
            store_sales=[
                StoreSales(store_id=125007, store_name="125007 MSK", quantity=11),
                StoreSales(store_id=125006, store_name="125006 KZN", quantity=6),
                StoreSales(store_id=130143, store_name="0130143 Mega", quantity=8),
            ]
        )

        fallback = [
            "125006 KZN-PC-Мега",
            "125007 MSK-PC-Гагаринский",
            "130143 MSK-PCM-Мега 2 Химки",
        ]
        store_id_map = {
            125006: "125006 KZN-PC-Мега",
            125007: "125007 MSK-PC-Гагаринский",
            130143: "130143 MSK-PCM-Мега 2 Химки",
        }

        priority = product.get_priority_order(fallback, store_id_map)

        # Should be ordered by sales: 125007 (11) > 130143 (8) > 125006 (6)
        assert priority[0] == "125007 MSK-PC-Гагаринский"
        assert priority[1] == "130143 MSK-PCM-Мега 2 Химки"
        assert priority[2] == "125006 KZN-PC-Мега"

    def test_get_priority_order_tiebreaker(self):
        """Test that ties are broken by fallback priority."""
        product = ProductSalesData(
            product_code="C5 21354",
            raw_name="_C5 21354_C5 21354",
            total_quantity=100,
            store_sales=[
                StoreSales(store_id=125007, store_name="125007 MSK", quantity=5),
                StoreSales(store_id=125006, store_name="125006 KZN", quantity=5),  # Same as above
                StoreSales(store_id=130143, store_name="0130143 Mega", quantity=3),
            ]
        )

        # Fallback has 125006 before 125007
        fallback = [
            "125006 KZN-PC-Мега",
            "125007 MSK-PC-Гагаринский",
            "130143 MSK-PCM-Мега 2 Химки",
        ]
        store_id_map = {
            125006: "125006 KZN-PC-Мега",
            125007: "125007 MSK-PC-Гагаринский",
            130143: "130143 MSK-PCM-Мега 2 Химки",
        }

        priority = product.get_priority_order(fallback, store_id_map)

        # Both 125006 and 125007 have 5 sales, so fallback order decides
        # 125006 comes first in fallback, so it should be first among the tie
        assert priority[0] == "125006 KZN-PC-Мега"
        assert priority[1] == "125007 MSK-PC-Гагаринский"
        assert priority[2] == "130143 MSK-PCM-Мега 2 Химки"


class TestSalesPriorityData:
    """Tests for SalesPriorityData."""

    def test_get_product_priority_found(self):
        """Test getting priority for a product that exists in sales data."""
        sales_data = SalesPriorityData(products={
            "C5 21354": ProductSalesData(
                product_code="C5 21354",
                raw_name="_C5 21354_C5 21354",
                total_quantity=100,
                store_sales=[
                    StoreSales(store_id=125007, store_name="125007", quantity=11),
                    StoreSales(store_id=125006, store_name="125006", quantity=6),
                ]
            )
        })

        fallback = ["125006 KZN-PC-Мега", "125007 MSK-PC-Гагаринский"]
        store_id_map = {
            125006: "125006 KZN-PC-Мега",
            125007: "125007 MSK-PC-Гагаринский",
        }

        priority, found = sales_data.get_product_priority("C5 21354", fallback, store_id_map)

        assert found is True
        assert priority[0] == "125007 MSK-PC-Гагаринский"  # Higher sales

    def test_get_product_priority_not_found(self):
        """Test getting priority for a product that doesn't exist returns fallback."""
        sales_data = SalesPriorityData(products={})

        fallback = ["125006 KZN-PC-Мега", "125007 MSK-PC-Гагаринский"]
        store_id_map = {}

        priority, found = sales_data.get_product_priority("UNKNOWN", fallback, store_id_map)

        assert found is False
        assert priority == fallback


class TestParseSalesFile:
    """Tests for parsing sales Excel files."""

    def test_parse_hierarchical_format(self):
        """Test parsing hierarchical Excel format."""
        # Create a mock Excel file in memory
        data = {
            0: [
                "Номенклатура",
                "_C5 21354.2110/1010_C5 21354.2110/1010",
                "0130143 MSK-PCM-Мега 2 Химки",
                "125007 MSK-PC-Гагаринский",
                "_C5 21354.2110/1105_C5 21354.2110/1105",
                "125006 KZN-PC-Мега",
            ],
            1: [None] * 6,
            2: [None] * 6,
            3: [
                "Количество",
                54,
                8,
                11,
                42,
                4,
            ],
        }
        df = pd.DataFrame(data)

        # Write to BytesIO
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, header=False)
        buffer.seek(0)

        # Parse
        result = parse_sales_file(buffer)

        assert len(result.products) == 2

        # Check first product
        product1 = result.products["C5 21354.2110/1010"]
        assert product1.total_quantity == 54
        assert len(product1.store_sales) == 2
        assert product1.store_sales[0].store_id == 130143
        assert product1.store_sales[0].quantity == 8
        assert product1.store_sales[1].store_id == 125007
        assert product1.store_sales[1].quantity == 11

        # Check second product
        product2 = result.products["C5 21354.2110/1105"]
        assert product2.total_quantity == 42
        assert len(product2.store_sales) == 1
        assert product2.store_sales[0].store_id == 125006
        assert product2.store_sales[0].quantity == 4
