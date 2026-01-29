"""Tests for InventoryBalancer (Script 2: Store-to-Store Balancing).

Balancing Rules:
1. Find stores with > threshold (default 2) items
2. Distribute excess to stores with 0 inventory (in priority order)
3. If all stores have inventory, excess goes to Stock
4. Takes from store with highest inventory first
"""

import pytest
from core.balancer import InventoryBalancer
from core.models import DistributionConfig
from tests.conftest import create_test_row, create_test_df, STORE_COLS


class TestInventoryBalancer:
    """Tests for store-to-store balancing (S5-S7)."""

    def test_one_store_surplus_distributes_to_empty(self, config):
        """S5: One store has >2, others empty → distributes surplus to empty stores.

        125007=5, others=0 → surplus (5-2=3) goes to empty stores in priority order.
        """
        rows = [
            create_test_row(
                "Product E", "Size M", stock=0,
                store_quantities={"125007 MSK-PC-Гагаринский": 5}
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Surplus = 5 - 2 = 3 items to distribute
        assert preview.total_quantity == 3

        # All transfers should come from 125007
        for transfer in preview.transfers:
            assert transfer.sender == "125007"  # Store code, not full name
            assert transfer.quantity == 1

        # Receivers should be the next stores in priority order
        receivers = [t.receiver for t in preview.transfers]
        assert "125008 MSK-PC-РИО Ленинский" in receivers
        assert "129877 MSK-PC-Мега 1 Теплый Стан" in receivers
        assert "130143 MSK-PCM-Мега 2 Химки" in receivers

    def test_multiple_stores_surplus_takes_highest_first(self, config):
        """S6: Multiple stores >2 → takes from highest quantity first.

        125007=4, 125008=6 → 125008 has higher qty so processes first.
        With 3 empty stores, 125008 sends 3 to empty stores, 1 to Stock (surplus=4).
        125007 sends its surplus (2) to Stock since empty stores already filled.
        """
        rows = [
            create_test_row(
                "Product F", "Size L", stock=0,
                store_quantities={
                    "125007 MSK-PC-Гагаринский": 4,
                    "125008 MSK-PC-РИО Ленинский": 6,
                }
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Total surplus: (6-2) + (4-2) = 4 + 2 = 6 items
        assert preview.total_quantity == 6

        # Find transfers from each sender
        transfers_from_125008 = [t for t in preview.transfers if "125008" in t.sender]
        transfers_from_125007 = [t for t in preview.transfers if "125007" in t.sender]

        # 125008 processes first: fills 3 empty stores + 1 to Stock = 4 transfers
        assert len(transfers_from_125008) == 4

        # 125007 processes second: all empty stores filled, so 1 transfer (2 units to Stock)
        assert len(transfers_from_125007) == 1
        assert transfers_from_125007[0].receiver == "Сток"
        assert transfers_from_125007[0].quantity == 2

    def test_surplus_to_stock_when_all_stores_have_inventory(self, config):
        """S7: All stores have inventory → surplus goes to Stock.

        125007=10, all others have 1 → surplus (10-2=8) goes to Stock.
        """
        store_quantities = {store: 1 for store in STORE_COLS}
        store_quantities["125007 MSK-PC-Гагаринский"] = 10

        rows = [
            create_test_row(
                "Product G", "Size S", stock=0,
                store_quantities=store_quantities
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Surplus = 10 - 2 = 8 items, all should go to Stock
        assert preview.total_quantity == 8

        # All transfers should go to Stock (Сток)
        for transfer in preview.transfers:
            assert transfer.receiver == "Сток"
            assert transfer.sender == "125007"  # Store code, not full name

    def test_no_surplus_no_transfers(self, config):
        """No store has > threshold → no transfers.

        All stores have exactly threshold (2) or less → nothing happens.
        """
        store_quantities = {store: 2 for store in STORE_COLS}

        rows = [
            create_test_row(
                "Product X", "Size M", stock=0,
                store_quantities=store_quantities
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        assert previews[0].total_quantity == 0

    def test_custom_threshold(self):
        """Respects custom balance threshold.

        With threshold=3, store with 4 items has only 1 surplus.
        """
        config = DistributionConfig(
            store_priority=STORE_COLS,
            excluded_stores=[],
            balance_threshold=3,  # Custom threshold
        )

        rows = [
            create_test_row(
                "Product Y", "Size L", stock=0,
                store_quantities={"125007 MSK-PC-Гагаринский": 4}
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        # Surplus = 4 - 3 = 1 item only
        assert previews[0].total_quantity == 1
