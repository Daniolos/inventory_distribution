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


class TestCompleteDistribution:
    """Tests for the optional complete distribution mode (Phase B + Phase C)."""

    OUTLET_STORE = "125839 - MSK-PC-Outlet Белая Дача"

    def _make_config(self, min_sizes_to_add: int = 3, complete: bool = True,
                     include_outlet: bool = True, excluded: list[str] = None):
        priority = list(STORE_COLS)
        if include_outlet:
            priority.append(self.OUTLET_STORE)
        return DistributionConfig(
            store_priority=priority,
            excluded_stores=excluded or [],
            balance_threshold=2,
            complete_distribution=complete,
            min_sizes_to_add=min_sizes_to_add,
        )

    def _add_outlet_col(self, rows: list[dict], outlet_qty: int = 0):
        for row in rows:
            row[self.OUTLET_STORE] = outlet_qty
        return rows

    def test_phase_b_bumps_store_with_one_item_to_two(self, config):
        """Store with existing 1 item gets a 2nd item when complete_distribution enabled."""
        # Stock=20 ensures Phase A completes with stock remaining for Phase B
        rows = [
            create_test_row(
                "Product A", "Size M", stock=20,
                store_quantities={"125007 MSK-PC-Гагаринский": 1},
            )
        ]
        df = create_test_df(rows)

        cfg = self._make_config(complete=True, include_outlet=False)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_to_first = [
            t for p in previews for t in p.transfers
            if t.receiver == "125007 MSK-PC-Гагаринский"
        ]
        # Phase A: skipped (has_stock). Phase B: +1 to reach 2.
        assert len(transfers_to_first) == 1

    def test_phase_b_bumps_store_that_received_in_phase_a(self, config):
        """Store that got 1 item in Phase A also gets a 2nd item in Phase B."""
        # Only 1 store available in priority + huge stock → Phase A gives 1, Phase B gives 2nd
        cfg = DistributionConfig(
            store_priority=["125007 MSK-PC-Гагаринский"],
            excluded_stores=[],
            complete_distribution=True,
            min_sizes_to_add=3,
        )
        rows = [create_test_row("Product A", "Size M", stock=5)]
        df = create_test_df(rows)

        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers = [t for p in previews for t in p.transfers]
        assert len(transfers) == 2
        assert all(t.receiver == "125007 MSK-PC-Гагаринский" for t in transfers)

    def test_phase_c_outlet_gets_up_to_three(self):
        """Outlet fills to 3 items per size when stock allows."""
        # Enough stock for Phase A (8 stores), Phase B (8 bumps), Phase C (+1 for outlet)
        rows = [create_test_row("Product A", "Size M", stock=20)]
        rows = self._add_outlet_col(rows)
        df = create_test_df(rows)

        cfg = self._make_config(complete=True)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_to_outlet = [
            t for p in previews for t in p.transfers
            if t.receiver == self.OUTLET_STORE
        ]
        # Phase A: 1, Phase B: +1, Phase C: +1 → 3 total
        assert len(transfers_to_outlet) == 3

    def test_phase_c_stops_when_stock_runs_out(self):
        """Outlet stops at remaining_stock boundary even if under the cap."""
        # Stock exactly matches number of non-outlet stores → outlet gets 0
        num_non_outlet_stores = len(STORE_COLS)
        rows = [create_test_row("Product A", "Size M", stock=num_non_outlet_stores)]
        rows = self._add_outlet_col(rows)
        df = create_test_df(rows)

        cfg = self._make_config(complete=True)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_to_outlet = [
            t for p in previews for t in p.transfers
            if t.receiver == self.OUTLET_STORE
        ]
        assert len(transfers_to_outlet) == 0

    def test_phase_c_respects_excluded_outlet(self):
        """Excluded outlet does not receive items in Phase C."""
        rows = [create_test_row("Product A", "Size M", stock=10)]
        rows = self._add_outlet_col(rows)
        df = create_test_df(rows)

        cfg = self._make_config(complete=True, excluded=[self.OUTLET_STORE])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_to_outlet = [
            t for p in previews for t in p.transfers
            if t.receiver == self.OUTLET_STORE
        ]
        assert len(transfers_to_outlet) == 0

    def test_complete_distribution_disabled_is_regression_safe(self, config):
        """complete_distribution=False keeps legacy behavior: max 1 per store per variant."""
        rows = [create_test_row("Product A", "Size M", stock=20)]
        df = create_test_df(rows)

        cfg = DistributionConfig(
            store_priority=STORE_COLS,
            excluded_stores=[],
            complete_distribution=False,
            min_sizes_to_add=3,
        )
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        # Legacy: exactly len(STORE_COLS) transfers, one per store
        assert previews[0].total_quantity == len(STORE_COLS)
        receivers = [t.receiver for t in previews[0].transfers]
        assert len(set(receivers)) == len(STORE_COLS)

    def test_phase_b_does_not_fire_for_stores_with_zero(self):
        """Phase B only bumps stores with exactly 1 item — stores with 0 remain untouched by B."""
        # Only one store available, no stock → Phase A gives 0, Phase B does nothing
        cfg = DistributionConfig(
            store_priority=["125007 MSK-PC-Гагаринский"],
            excluded_stores=[],
            complete_distribution=True,
            min_sizes_to_add=3,
        )
        rows = [create_test_row("Product A", "Size M", stock=0)]
        df = create_test_df(rows)

        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)
        assert sum(p.total_quantity for p in previews) == 0


class TestConfigurableMinSizesToAdd:
    """Tests for the configurable MIN_SIZES_TO_ADD threshold."""

    def test_min_sizes_to_add_1_allows_single_size_transfer(self, config):
        """With threshold=1, even a single available size triggers transfer for 4+ size product."""
        # Product with 4 total sizes, store has 0 — min_sizes rule applies.
        # Only 1 size has stock. Default (3): nothing transfers. With 1: transfer happens.
        rows = [
            create_test_row(
                "MinSize Product", "Size S", stock=5,
                store_quantities={"125007 MSK-PC-Гагаринский": 0},
            ),
            create_test_row(
                "MinSize Product", "Size M", stock=0,
                store_quantities={"125007 MSK-PC-Гагаринский": 0},
            ),
            create_test_row(
                "MinSize Product", "Size L", stock=0,
                store_quantities={"125007 MSK-PC-Гагаринский": 0},
            ),
            create_test_row(
                "MinSize Product", "Size XL", stock=0,
                store_quantities={"125007 MSK-PC-Гагаринский": 0},
            ),
        ]
        df = create_test_df(rows)

        cfg = DistributionConfig(
            store_priority=STORE_COLS,
            excluded_stores=[],
            complete_distribution=False,
            min_sizes_to_add=1,
        )
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        total = sum(p.total_quantity for p in previews)
        assert total > 0
        # Ensure first store received the single available size
        first_store_transfers = [
            t for p in previews for t in p.transfers
            if t.receiver == "125007 MSK-PC-Гагаринский"
        ]
        assert len(first_store_transfers) == 1

    def test_min_sizes_to_add_2_allows_two_size_transfer(self, config):
        """With threshold=2, 2 available sizes suffice; default 3 would skip."""
        rows = [
            create_test_row("MinSize Product", "Size S", stock=5),
            create_test_row("MinSize Product", "Size M", stock=5),
            create_test_row("MinSize Product", "Size L", stock=0),
            create_test_row("MinSize Product", "Size XL", stock=0),
        ]
        df = create_test_df(rows)

        cfg = DistributionConfig(
            store_priority=STORE_COLS,
            excluded_stores=[],
            complete_distribution=False,
            min_sizes_to_add=2,
        )
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        first_store_transfers = [
            t for p in previews for t in p.transfers
            if t.receiver == "125007 MSK-PC-Гагаринский"
        ]
        # Both available sizes transferred
        assert len(first_store_transfers) == 2

    def test_min_sizes_to_add_3_default_skips_when_two_sizes(self, config):
        """Regression: default threshold=3 still skips when only 2 sizes available."""
        rows = [
            create_test_row("MinSize Product", "Size S", stock=5),
            create_test_row("MinSize Product", "Size M", stock=5),
            create_test_row("MinSize Product", "Size L", stock=0),
            create_test_row("MinSize Product", "Size XL", stock=0),
        ]
        df = create_test_df(rows)

        # Default min_sizes_to_add = 3
        cfg = DistributionConfig(
            store_priority=STORE_COLS,
            excluded_stores=[],
            complete_distribution=False,
            min_sizes_to_add=3,
        )
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        first_store_transfers = [
            t for p in previews for t in p.transfers
            if t.receiver == "125007 MSK-PC-Гагаринский"
        ]
        assert len(first_store_transfers) == 0


class TestExcelRowCalculation:
    """Tests for correct Excel row number calculation.

    Excel structure (with header_row=6, 0-indexed):
    - Row 7 (index 6): Header row
    - Row 8 (index 7): Sub-header row (skipped with skiprows)
    - Row 9 (index 8): First data row → pandas index 0
    - Row 10 (index 9): Second data row → pandas index 1
    """

    def test_row_index_calculation_single_row(self, config):
        """First data row should have row_index = header_row + 3."""
        rows = [create_test_row("Product A", "Size M", stock=5)]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        # header_row=6 (0-indexed) means Excel row 7 is the header
        previews = distributor.preview(df, source="stock", header_row=6)

        assert len(previews) == 1
        # First data row: header_row(6) + 3 + pandas_index(0) = 9
        assert previews[0].row_index == 9

    def test_row_index_calculation_multiple_rows(self, config):
        """Multiple rows should have consecutive row_index values."""
        rows = [
            create_test_row("Product A", "Size S", stock=1),
            create_test_row("Product A", "Size M", stock=1),
            create_test_row("Product A", "Size L", stock=1),
        ]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        previews = distributor.preview(df, source="stock", header_row=6)

        assert len(previews) == 3
        # Rows should be 9, 10, 11 (header_row + 3 + index)
        row_indices = sorted([p.row_index for p in previews])
        assert row_indices == [9, 10, 11]

    def test_row_index_with_different_header_row(self, config):
        """Row index should adjust based on header_row parameter."""
        rows = [create_test_row("Product A", "Size M", stock=5)]
        df = create_test_df(rows)

        distributor = StockDistributor(config)
        # header_row=10 means Excel row 11 is the header
        previews = distributor.preview(df, source="stock", header_row=10)

        assert len(previews) == 1
        # First data row: header_row(10) + 3 + pandas_index(0) = 13
        assert previews[0].row_index == 13
