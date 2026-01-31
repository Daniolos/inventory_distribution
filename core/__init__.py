"""Core module for inventory distribution logic."""

from .models import (
    Transfer,
    TransferPreview,
    TransferResult,
    DistributionConfig,
    StoreSales,
    ProductSalesData,
    SalesPriorityData,
    extract_store_id,
    build_store_id_map,
    get_stock_value,
    count_sizes_with_stock,
    should_apply_min_sizes_rule,
)
from .sales_parser import (
    extract_product_code_from_sales,
    extract_product_code_from_input,
    parse_sales_file,
)
from .file_loader import (
    find_header_row,
    load_excel_with_header,
    validate_required_columns,
)
from .filters import (
    format_filter_value,
    extract_article_name,
    get_unique_article_types,
    get_unique_collections,
    get_unique_additional_names,
    apply_article_type_filter,
    apply_collection_filter,
    apply_additional_name_filter,
    apply_all_filters,
)
from .distributor import StockDistributor
from .balancer import InventoryBalancer

__all__ = [
    # Models
    "Transfer",
    "TransferPreview",
    "TransferResult",
    "DistributionConfig",
    "StoreSales",
    "ProductSalesData",
    "SalesPriorityData",
    "extract_store_id",
    "build_store_id_map",
    "get_stock_value",
    "count_sizes_with_stock",
    "should_apply_min_sizes_rule",
    # Sales parser
    "extract_product_code_from_sales",
    "extract_product_code_from_input",
    "parse_sales_file",
    # File loader
    "find_header_row",
    "load_excel_with_header",
    "validate_required_columns",
    # Filters
    "format_filter_value",
    "extract_article_name",
    "get_unique_article_types",
    "get_unique_collections",
    "get_unique_additional_names",
    "apply_article_type_filter",
    "apply_collection_filter",
    "apply_additional_name_filter",
    "apply_all_filters",
    # Distributors
    "StockDistributor",
    "InventoryBalancer",
]

