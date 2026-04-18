"""Tests for StockDistributor (Stock/Photo → Stores).

Phased distribution algorithm:
- Phase 1: Reach target_sizes_filled per store (all-or-nothing, 1 unit per size)
- Phase 2: Top up each filled size to 2 units (if units_per_size >= 2)
- Phase 3: Top up each filled size to 3 units (if units_per_size >= 3)

Phases iterate stores in priority order and each phase completes for every store
before the next begins (fair distribution).
"""

import pytest
from core.distributor import StockDistributor
from core.models import DistributionConfig
from tests.conftest import create_test_row, create_test_df, STORE_COLS


def _make_config(target_sizes_filled: int = 3, units_per_size: int = 1,
                 min_product_sizes: int = 1, max_product_sizes: int = 99,
                 store_priority=None, excluded_stores=None) -> DistributionConfig:
    return DistributionConfig(
        store_priority=store_priority if store_priority is not None else STORE_COLS,
        excluded_stores=excluded_stores or [],
        balance_threshold=2,
        target_sizes_filled=target_sizes_filled,
        units_per_size=units_per_size,
        min_product_sizes=min_product_sizes,
        max_product_sizes=max_product_sizes,
    )


class TestPhase1TargetReached:
    """Store reaches the size-count target → Phase 1 transfers."""

    def test_target_met_transfers_all_transferable_sizes(self):
        """Target=3, product has 5 sizes, first store has 0: gets all 5 sizes (not just 3)."""
        rows = [
            create_test_row("P", "S1", stock=10),
            create_test_row("P", "S2", stock=10),
            create_test_row("P", "S3", stock=10),
            create_test_row("P", "S4", stock=10),
            create_test_row("P", "S5", stock=10),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, units_per_size=1)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        first_store = STORE_COLS[0]
        transfers_first = [t for p in previews for t in p.transfers if t.receiver == first_store]
        assert len(transfers_first) == 5

    def test_target_already_met_no_phase1_transfer(self):
        """Store has 3 sizes already, target=3: Phase 1 does nothing for that store."""
        rows = [
            create_test_row("P", "S1", stock=10, store_quantities={STORE_COLS[0]: 1}),
            create_test_row("P", "S2", stock=10, store_quantities={STORE_COLS[0]: 1}),
            create_test_row("P", "S3", stock=10, store_quantities={STORE_COLS[0]: 1}),
            create_test_row("P", "S4", stock=10),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, units_per_size=1)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        first_store = STORE_COLS[0]
        transfers_first = [t for p in previews for t in p.transfers if t.receiver == first_store]
        assert len(transfers_first) == 0

    def test_partial_fill_reaches_target(self):
        """Store has 1 size, target=3, 2 transferable sizes with stock: gets both → reaches target."""
        rows = [
            create_test_row("P", "S1", stock=0, store_quantities={STORE_COLS[0]: 1}),
            create_test_row("P", "S2", stock=10),
            create_test_row("P", "S3", stock=10),
            create_test_row("P", "S4", stock=0),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, units_per_size=1,
                           store_priority=[STORE_COLS[0]])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[0]]
        assert len(transfers) == 2


class TestPhase1TargetNotReached:
    """Store cannot reach target → all-or-nothing skip."""

    def test_insufficient_sizes_skips_store(self):
        """Target=3, product has 2 sizes, store has 0: 0 transfers, target_not_reached flag set."""
        rows = [
            create_test_row("P", "S1", stock=10),
            create_test_row("P", "S2", stock=10),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, units_per_size=1,
                           store_priority=[STORE_COLS[0]])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        total_transfers = sum(len(p.transfers) for p in previews)
        assert total_transfers == 0
        assert all(p.target_not_reached for p in previews)
        assert any(s.reason == "target_not_reached" for p in previews for s in p.skipped_stores)

    def test_skip_when_stock_depletes_mid_iteration(self):
        """Store P2 can't reach target because P1 consumed the stock → P2 skipped with flag."""
        rows = [
            create_test_row("P", "S1", stock=1),
            create_test_row("P", "S2", stock=1),
            create_test_row("P", "S3", stock=1),
        ]
        df = create_test_df(rows)

        # Only first two stores in priority
        cfg = _make_config(target_sizes_filled=3, units_per_size=1,
                           store_priority=[STORE_COLS[0], STORE_COLS[1]])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_p1 = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[0]]
        transfers_p2 = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[1]]
        assert len(transfers_p1) == 3
        assert len(transfers_p2) == 0
        assert any(p.target_not_reached for p in previews)


class TestPhase2And3TopUp:
    """Phase 2 (1→2 units) and Phase 3 (2→3 units)."""

    def test_units_per_size_2_tops_up_after_phase1(self):
        """units=2: every store that received 1 unit in Phase 1 gets a 2nd unit."""
        rows = [
            create_test_row("P", "S1", stock=20),
            create_test_row("P", "S2", stock=20),
            create_test_row("P", "S3", stock=20),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, units_per_size=2,
                           store_priority=[STORE_COLS[0]])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_first = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[0]]
        # Phase 1: 3 transfers (1 per size) + Phase 2: 3 transfers (+1 per size) = 6
        assert len(transfers_first) == 6

    def test_units_per_size_3_tops_up_to_three(self):
        """units=3: each filled size gets topped up to 3 units."""
        rows = [
            create_test_row("P", "S1", stock=20),
            create_test_row("P", "S2", stock=20),
            create_test_row("P", "S3", stock=20),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, units_per_size=3,
                           store_priority=[STORE_COLS[0]])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_first = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[0]]
        # Phase 1: 3, Phase 2: +3, Phase 3: +3 = 9
        assert len(transfers_first) == 9

    def test_phase2_tops_up_existing_one_unit_sizes(self):
        """Store already has 1 unit on some sizes (not transferred in Phase 1): Phase 2 tops to 2."""
        rows = [
            create_test_row("P", "S1", stock=20, store_quantities={STORE_COLS[0]: 1}),
            create_test_row("P", "S2", stock=20, store_quantities={STORE_COLS[0]: 1}),
            create_test_row("P", "S3", stock=20, store_quantities={STORE_COLS[0]: 1}),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, units_per_size=2,
                           store_priority=[STORE_COLS[0]])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_first = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[0]]
        # Phase 1 does nothing (target met). Phase 2 bumps each of 3 sizes from 1 → 2 = 3 transfers
        assert len(transfers_first) == 3


class TestFairness:
    """All stores must complete Phase 1 before any moves to Phase 2."""

    def test_phase1_completes_for_all_stores_before_phase2(self):
        """Low-priority store still gets Phase 1 baseline before high-priority gets Phase 2 bump."""
        rows = [
            create_test_row("P", "S1", stock=4),
            create_test_row("P", "S2", stock=4),
            create_test_row("P", "S3", stock=4),
        ]
        df = create_test_df(rows)

        # Two stores in priority, units=2, stock=4 per row
        # Phase 1: P1 gets 3 (1 per size), P2 gets 3 (1 per size) → 6 used
        # Phase 2: 4-2=2 left per row (wait: 4-2 = 2 remaining per row)
        # Actually stock=4 per row. Phase 1 uses 2 per row (one for each store). 2 remain.
        # Phase 2 bumps P1 on each row (+1), then P2 (+1). Uses remaining 2 per row.
        cfg = _make_config(target_sizes_filled=3, units_per_size=2,
                           store_priority=[STORE_COLS[0], STORE_COLS[1]])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_p1 = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[0]]
        transfers_p2 = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[1]]
        # Fair: both stores get 6 (3 in Phase 1 + 3 in Phase 2)
        assert len(transfers_p1) == 6
        assert len(transfers_p2) == 6

    def test_phase1_priority_matters_when_stock_tight(self):
        """Tight stock: P1 gets Phase 1 first; P2 must still reach target or be skipped."""
        rows = [
            create_test_row("P", "S1", stock=2),
            create_test_row("P", "S2", stock=2),
            create_test_row("P", "S3", stock=2),
        ]
        df = create_test_df(rows)

        # Stock per row=2, target=3, 3 stores. P1 gets 3, P2 gets 3, P3 skipped.
        cfg = _make_config(target_sizes_filled=3, units_per_size=1,
                           store_priority=[STORE_COLS[0], STORE_COLS[1], STORE_COLS[2]])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_p1 = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[0]]
        transfers_p2 = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[1]]
        transfers_p3 = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[2]]
        assert len(transfers_p1) == 3
        assert len(transfers_p2) == 3
        assert len(transfers_p3) == 0


class TestProductSizeRangeFilter:
    """min_product_sizes / max_product_sizes filter products by their total size count."""

    def test_product_below_range_filtered_out(self):
        """Product has 2 sizes, min_product_sizes=4: product skipped entirely."""
        rows = [
            create_test_row("Small", "S1", stock=10),
            create_test_row("Small", "S2", stock=10),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=1, min_product_sizes=4)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        assert sum(len(p.transfers) for p in previews) == 0
        assert all(p.skip_reason for p in previews)

    def test_product_above_range_filtered_out(self):
        """Product has 5 sizes, max_product_sizes=3: product skipped."""
        rows = [create_test_row("Big", f"S{i}", stock=10) for i in range(5)]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=1, max_product_sizes=3)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        assert sum(len(p.transfers) for p in previews) == 0

    def test_product_inside_range_distributed(self):
        """Product size count within [min, max] — normal processing."""
        rows = [create_test_row("P", f"S{i}", stock=10) for i in range(4)]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, min_product_sizes=4, max_product_sizes=10)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        assert sum(len(p.transfers) for p in previews) > 0


class TestSingleSizeProducts:
    """With target=1 and range filter, single-size products are distributable."""

    def test_single_size_target_1_distributes(self):
        """Target=1 and 1-size product: store gets that single size."""
        rows = [create_test_row("Single", "OneSize", stock=5)]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=1, units_per_size=1,
                           min_product_sizes=1, max_product_sizes=1)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        # Each of the 5 stock units goes to a different store
        assert sum(len(p.transfers) for p in previews) == 5


class TestOutletAsFilter:
    """Outlet use-case: filter to only outlet store + units=3 replaces the old Phase C."""

    OUTLET_STORE = "125839 - MSK-PC-Outlet Белая Дача"

    def test_only_outlet_store_gets_3_units_per_size(self):
        """With only Outlet in priority and units=3, Outlet receives 3 units per size."""
        rows = [
            create_test_row("P", "S1", stock=20),
            create_test_row("P", "S2", stock=20),
            create_test_row("P", "S3", stock=20),
        ]
        # Add outlet column
        for row in rows:
            row[self.OUTLET_STORE] = 0
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, units_per_size=3,
                           store_priority=[self.OUTLET_STORE])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_to_outlet = [t for p in previews for t in p.transfers if t.receiver == self.OUTLET_STORE]
        # 3 sizes × 3 units = 9
        assert len(transfers_to_outlet) == 9


class TestExcludedStores:
    """Excluded stores must not receive anything and must be tracked."""

    def test_excluded_store_receives_nothing(self):
        rows = [
            create_test_row("P", "S1", stock=10),
            create_test_row("P", "S2", stock=10),
            create_test_row("P", "S3", stock=10),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, excluded_stores=[STORE_COLS[0]])
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        transfers_excluded = [t for p in previews for t in p.transfers if t.receiver == STORE_COLS[0]]
        assert len(transfers_excluded) == 0
        assert any(s.reason == "excluded" and s.store_name == STORE_COLS[0]
                   for p in previews for s in p.skipped_stores)


class TestPhotoStock:
    def test_photo_source_uses_photo_column(self):
        rows = [
            create_test_row("P", "S1", stock=0, photo_stock=10),
            create_test_row("P", "S2", stock=0, photo_stock=10),
            create_test_row("P", "S3", stock=0, photo_stock=10),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3, store_priority=[STORE_COLS[0]])
        previews = StockDistributor(cfg).preview(df, source="photo", header_row=7)

        assert all(t.sender == "Фото" for p in previews for t in p.transfers)
        assert sum(len(p.transfers) for p in previews) == 3


class TestEmptyStockNoDistribution:
    def test_zero_stock_produces_no_transfers(self):
        rows = [create_test_row("P", f"S{i}", stock=0) for i in range(4)]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=7)

        assert sum(len(p.transfers) for p in previews) == 0


class TestExcelRowCalculation:
    """Excel row numbers: header_row + 3 + pandas_index."""

    def test_row_index_single_row(self):
        rows = [create_test_row("P", "S1", stock=5)]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=1, min_product_sizes=1, max_product_sizes=1)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=6)

        assert len(previews) == 1
        assert previews[0].row_index == 9

    def test_row_index_multiple_rows(self):
        rows = [
            create_test_row("P", "S1", stock=1),
            create_test_row("P", "S2", stock=1),
            create_test_row("P", "S3", stock=1),
        ]
        df = create_test_df(rows)

        cfg = _make_config(target_sizes_filled=3)
        previews = StockDistributor(cfg).preview(df, source="stock", header_row=6)

        assert sorted([p.row_index for p in previews]) == [9, 10, 11]
