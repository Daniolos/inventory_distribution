"""Tests for StockDistributor (Script 1: Stock/Photo to Stores).

Distribution Rules:
1. Normal rule: If store has 2+ sizes of a product → distribute 1 item per variant where store has 0
2. Minimum sizes rule: If store has 0-1 sizes of a product:
   - Only transfer if 3+ sizes are available in stock
   - Transfer ALL available sizes (not just 3)
   - If < 3 sizes available → transfer nothing (all or nothing)
"""

import pytest
from core.distributor import StockDistributor
from core.models import DistributionConfig
from tests.conftest import create_test_row, create_test_df, STORE_COLS


class TestStockDistributorBasic:
    """Basic distribution scenarios (S1-S4)."""

    def test_stock_full_all_stores_empty(self, config):
        """S1: Stock=5, all stores=0 → distributes 1 to each store (max 5 stores).

        With 5 items in stock and 5 empty stores, each store gets 1 item.
        """
        rows = [create_test_row("Product A", "Size M", stock=5)]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="stock", header_row=7)

        # Should have 1 preview (for the single row)
        assert len(previews) == 1
        preview = previews[0]

        # Should have 5 transfers (one per store)
        assert len(preview.transfers) == 5
        assert preview.total_quantity == 5

        # Each transfer should be 1 item
        for transfer in preview.transfers:
            assert transfer.quantity == 1
            assert transfer.sender == "Сток"

    def test_stock_full_some_stores_have(self, config):
        """S2: Stock=3, some stores already have 1 → only distribute to empty stores.

        Stores with existing stock are skipped.
        """
        rows = [
            create_test_row(
                "Product B", "Size L", stock=3,
                store_quantities={
                    "125007 MSK-PC-Гагаринский": 1,
                    "125008 MSK-PC-РИО Ленинский": 1,
                }
            )
        ]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="stock", header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Should have 3 transfers (to stores without stock)
        assert len(preview.transfers) == 3

        # Verify no transfers to stores that already have stock
        receivers = [t.receiver for t in preview.transfers]
        assert "125007 MSK-PC-Гагаринский" not in receivers
        assert "125008 MSK-PC-РИО Ленинский" not in receivers

    def test_stock_empty_no_distribution(self, config):
        """S3: Stock=0 → nothing happens.

        No distribution when source is empty.
        """
        rows = [create_test_row("Product C", "Size S", stock=0)]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="stock", header_row=7)

        # Should still have 1 preview, but with no transfers
        assert len(previews) == 1
        assert previews[0].total_quantity == 0

    def test_all_stores_full_no_distribution(self, config):
        """S4: Stock=3, all stores have 1 → no distribution.

        When all stores already have stock, nothing is distributed.
        """
        store_quantities = {store: 1 for store in STORE_COLS}
        rows = [create_test_row("Product D", "Size XL", stock=3, store_quantities=store_quantities)]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="stock", header_row=7)

        assert len(previews) == 1
        assert previews[0].total_quantity == 0


class TestMinimumSizesRule:
    """Tests for the minimum sizes rule (B1-B4).

    Rule: If store has 0-1 sizes of a product:
    - Only transfer if 3+ sizes are available
    - Transfer ALL available sizes
    - If < 3 sizes → transfer nothing
    """

    def test_2_sizes_no_transfer(self, config):
        """B1: Product with only 2 sizes in stock → normal distribution applies.

        Products with <4 sizes don't use minimum-sizes rule, so normal distribution happens.
        Each size will be transferred to empty stores.
        """
        # Same product, 2 different sizes
        rows = [
            create_test_row("MinSize Product", "Size S", stock=1),
            create_test_row("MinSize Product", "Size M", stock=1),
        ]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="stock", header_row=7)

        # With <4 sizes, normal distribution applies - both rows should have transfers
        total_transfers = sum(p.total_quantity for p in previews)
        assert total_transfers == 2  # Each size goes to one store

    def test_3_sizes_transfers_all(self, config):
        """B2: Product with exactly 3 sizes → all 3 transfer.

        When exactly 3 sizes are available, all 3 are transferred.
        """
        rows = [
            create_test_row("MinSize Product", "Size S", stock=1),
            create_test_row("MinSize Product", "Size M", stock=1),
            create_test_row("MinSize Product", "Size L", stock=1),
        ]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="stock", header_row=7)

        # First store (125007) should receive all 3 sizes
        transfers_to_first_store = []
        for preview in previews:
            for transfer in preview.transfers:
                if transfer.receiver == "125007 MSK-PC-Гагаринский":
                    transfers_to_first_store.append(transfer)

        assert len(transfers_to_first_store) == 3

    def test_5_sizes_transfers_all(self, config):
        """B3: Product with 5 sizes → all 5 transfer (not just 3).

        This is the bug fix verification: ALL sizes should transfer, not just 3.
        """
        rows = [
            create_test_row("MinSize Product", "Size XS", stock=1),
            create_test_row("MinSize Product", "Size S", stock=1),
            create_test_row("MinSize Product", "Size M", stock=1),
            create_test_row("MinSize Product", "Size L", stock=1),
            create_test_row("MinSize Product", "Size XL", stock=1),
        ]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="stock", header_row=7)

        # First store (125007) should receive ALL 5 sizes
        transfers_to_first_store = []
        for preview in previews:
            for transfer in preview.transfers:
                if transfer.receiver == "125007 MSK-PC-Гагаринский":
                    transfers_to_first_store.append(transfer)

        # Critical assertion: must be 5, not 3
        assert len(transfers_to_first_store) == 5

    def test_store_has_2_sizes_normal_rule(self, config):
        """B4: Store already has 2+ sizes → normal rule applies (1 per missing size).

        When store has 2+ sizes, the minimum sizes rule doesn't apply.
        Instead, normal distribution happens: 1 item per variant where store has 0.
        """
        rows = [
            # Store 125007 already has Size S and Size M
            create_test_row(
                "Product X", "Size S", stock=1,
                store_quantities={"125007 MSK-PC-Гагаринский": 1}
            ),
            create_test_row(
                "Product X", "Size M", stock=1,
                store_quantities={"125007 MSK-PC-Гагаринский": 1}
            ),
            # Size L and XL are missing from store
            create_test_row("Product X", "Size L", stock=1),
            create_test_row("Product X", "Size XL", stock=1),
        ]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="stock", header_row=7)

        # Store 125007 should receive Size L and Size XL (not S and M)
        transfers_to_first_store = []
        for preview in previews:
            for transfer in preview.transfers:
                if transfer.receiver == "125007 MSK-PC-Гагаринский":
                    transfers_to_first_store.append((preview.variant, transfer))

        # Should receive 2 sizes (L and XL), not 0 (min rule) and not 4 (all)
        assert len(transfers_to_first_store) == 2

        # Verify it's the missing sizes
        variants_received = [t[0] for t in transfers_to_first_store]
        assert "Size L" in variants_received
        assert "Size XL" in variants_received


class TestPhotoStockDistribution:
    """Tests for Photo Stock source (S8)."""

    def test_photo_stock_distribution(self, config):
        """S8: Photo Stock=3, Stock=0, all empty → distributes from Photo.

        Photo Stock is a separate source that can be selected.
        """
        rows = [create_test_row("Product H", "Size M", stock=0, photo_stock=3)]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="photo", header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Should have 3 transfers from Фото
        assert preview.total_quantity == 3
        for transfer in preview.transfers:
            assert transfer.sender == "Фото"
