"""Tests for InventoryBalancer (Script 2: Store-to-Store Balancing).

Balancing Rules (NEW):
1. Find stores with > threshold (default 2) items
2. Excess goes directly to Stock (no distribution to other stores)
3. Exception: Store pairs can balance between each other first
4. Takes from store with highest inventory first
"""

import pytest
from core.balancer import InventoryBalancer
from core.models import DistributionConfig
from tests.conftest import create_test_row, create_test_df, STORE_COLS


class TestUnpairedStoreBalancing:
    """Tests for stores that are NOT in a balance pair."""

    def test_unpaired_store_excess_goes_directly_to_stock(self, config_with_pairs):
        """Unpaired store with excess sends ALL to Stock, not to other stores.

        125007 (not in a pair) has 5 items → surplus (5-2=3) goes to Stock.
        """
        rows = [
            create_test_row(
                "Product A", "Size M", stock=0,
                store_quantities={"125007 MSK-PC-Гагаринский": 5}
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # ALL excess (5-2=3) should go to Stock
        assert preview.total_quantity == 3
        assert len(preview.transfers) == 1
        assert preview.transfers[0].receiver == "Сток"
        assert preview.transfers[0].sender == "125007"
        assert preview.transfers[0].quantity == 3

    def test_multiple_unpaired_stores_all_to_stock(self, config_with_pairs):
        """Multiple unpaired stores with excess → each sends all to Stock.

        125007=4, 130143=5 → both unpaired, all excess to Stock.
        """
        rows = [
            create_test_row(
                "Product B", "Size L", stock=0,
                store_quantities={
                    "125007 MSK-PC-Гагаринский": 4,  # surplus = 2
                    "130143 MSK-PCM-Мега 2 Химки": 5,  # surplus = 3
                }
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Total surplus: (4-2) + (5-2) = 2 + 3 = 5 items
        assert preview.total_quantity == 5

        # All transfers should go to Stock
        for transfer in preview.transfers:
            assert transfer.receiver == "Сток"


class TestPairedStoreBalancing:
    """Tests for stores that ARE in a balance pair."""

    def test_paired_store_sends_to_partner_first_then_stock(self, config_with_pairs):
        """Paired store sends 1 to partner (if partner has 0), rest to Stock.

        125004 (paired with 125005) has 5, 125005 has 0.
        → 1 goes to 125005, 2 go to Stock.
        """
        rows = [
            create_test_row(
                "Product C", "Size S", stock=0,
                store_quantities={
                    "125004 EKT-PC-Гринвич": 5,  # Paired with 125005
                    "125005 EKT-PC-Мега": 0,     # Partner has 0
                }
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Excess = 5-2 = 3: 1 to partner, 2 to Stock
        assert preview.total_quantity == 3

        transfers_to_partner = [
            t for t in preview.transfers if "125005" in t.receiver
        ]
        transfers_to_stock = [
            t for t in preview.transfers if t.receiver == "Сток"
        ]

        assert len(transfers_to_partner) == 1
        assert transfers_to_partner[0].quantity == 1

        assert len(transfers_to_stock) == 1
        assert transfers_to_stock[0].quantity == 2

    def test_paired_store_partner_has_inventory_all_to_stock(self, config_with_pairs):
        """If partner already has inventory, all excess goes to Stock.

        125004 has 5, 125005 has 1 → all excess to Stock (partner not empty).
        """
        rows = [
            create_test_row(
                "Product D", "Size M", stock=0,
                store_quantities={
                    "125004 EKT-PC-Гринвич": 5,
                    "125005 EKT-PC-Мега": 1,  # Partner already has stock
                }
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Excess = 5-2 = 3, ALL to Stock (partner has inventory)
        assert preview.total_quantity == 3
        assert len(preview.transfers) == 1
        assert preview.transfers[0].receiver == "Сток"
        assert preview.transfers[0].quantity == 3

    def test_both_paired_stores_have_excess(self, config_with_pairs):
        """When both paired stores have excess, neither can receive, all to Stock.

        125004=5, 125005=4 → both have excess, neither is empty, all to Stock.
        """
        rows = [
            create_test_row(
                "Product E", "Size L", stock=0,
                store_quantities={
                    "125004 EKT-PC-Гринвич": 5,  # Excess = 3
                    "125005 EKT-PC-Мега": 4,     # Excess = 2
                }
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Total excess = 3 + 2 = 5, all to Stock
        assert preview.total_quantity == 5

        # All transfers should go to Stock
        for transfer in preview.transfers:
            assert transfer.receiver == "Сток"

    def test_second_pair_balances_correctly(self, config_with_pairs):
        """The second pair (125008 ↔ 129877) also balances correctly.

        125008 has 6, 129877 has 0 → 1 to 129877, 3 to Stock.
        """
        rows = [
            create_test_row(
                "Product F", "Size XL", stock=0,
                store_quantities={
                    "125008 MSK-PC-РИО Ленинский": 6,
                    "129877 MSK-PC-Мега 1 Теплый Стан": 0,
                }
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Excess = 6-2 = 4: 1 to partner, 3 to Stock
        assert preview.total_quantity == 4

        transfers_to_partner = [
            t for t in preview.transfers if "129877" in t.receiver
        ]
        transfers_to_stock = [
            t for t in preview.transfers if t.receiver == "Сток"
        ]

        assert len(transfers_to_partner) == 1
        assert transfers_to_partner[0].quantity == 1

        assert len(transfers_to_stock) == 1
        assert transfers_to_stock[0].quantity == 3


class TestExcludedStoresInBalancing:
    """Tests that excluded stores are properly handled."""

    def test_excluded_partner_all_to_stock(self, config_with_pairs):
        """If partner is excluded, all excess goes to Stock.

        125004 has 5, partner 125005 is excluded → all to Stock.
        """
        config = DistributionConfig(
            store_priority=STORE_COLS,
            excluded_stores=["125005 EKT-PC-Мега"],
            balance_threshold=2,
            store_balance_pairs=config_with_pairs.store_balance_pairs,
        )

        rows = [
            create_test_row(
                "Product G", "Size S", stock=0,
                store_quantities={
                    "125004 EKT-PC-Гринвич": 5,
                    "125005 EKT-PC-Мега": 0,
                }
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # All excess to Stock (partner is excluded)
        assert preview.total_quantity == 3
        assert len(preview.transfers) == 1
        assert preview.transfers[0].receiver == "Сток"

    def test_excluded_store_cannot_send(self, config_with_pairs):
        """Excluded store with excess cannot send anything."""
        config = DistributionConfig(
            store_priority=STORE_COLS,
            excluded_stores=["125007 MSK-PC-Гагаринский"],
            balance_threshold=2,
            store_balance_pairs=config_with_pairs.store_balance_pairs,
        )

        rows = [
            create_test_row(
                "Product H", "Size M", stock=0,
                store_quantities={
                    "125007 MSK-PC-Гагаринский": 10,  # Excluded, has lots of excess
                }
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        # No transfers because the only store with excess is excluded
        assert previews[0].total_quantity == 0


class TestEdgeCases:
    """Tests for edge cases and general functionality."""

    def test_no_surplus_no_transfers(self, config_with_pairs):
        """No store has > threshold → no transfers.

        All stores have exactly threshold (2) or less → nothing happens.
        """
        store_quantities = {store: 2 for store in STORE_COLS}

        rows = [
            create_test_row(
                "Product I", "Size M", stock=0,
                store_quantities=store_quantities
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        assert previews[0].total_quantity == 0

    def test_custom_threshold(self, config_with_pairs):
        """Respects custom balance threshold.

        With threshold=3, store with 4 items has only 1 surplus → goes to Stock.
        """
        config = DistributionConfig(
            store_priority=STORE_COLS,
            excluded_stores=[],
            balance_threshold=3,
            store_balance_pairs=config_with_pairs.store_balance_pairs,
        )

        rows = [
            create_test_row(
                "Product J", "Size L", stock=0,
                store_quantities={"125007 MSK-PC-Гагаринский": 4}  # Not paired
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        # Surplus = 4 - 3 = 1 item, goes to Stock
        assert previews[0].total_quantity == 1
        assert previews[0].transfers[0].receiver == "Сток"

    def test_all_stores_have_inventory_to_stock(self, config_with_pairs):
        """All stores have inventory → surplus goes to Stock.

        125007=10, all others have 1 → surplus (10-2=8) goes to Stock.
        """
        store_quantities = {store: 1 for store in STORE_COLS}
        store_quantities["125007 MSK-PC-Гагаринский"] = 10

        rows = [
            create_test_row(
                "Product K", "Size S", stock=0,
                store_quantities=store_quantities
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # Surplus = 10 - 2 = 8 items, all to Stock
        assert preview.total_quantity == 8
        assert len(preview.transfers) == 1
        assert preview.transfers[0].receiver == "Сток"
        assert preview.transfers[0].sender == "125007"

    def test_without_pairs_configured_all_to_stock(self, config):
        """Without store pairs configured, all excess goes to Stock.

        Using config fixture (no pairs), even paired store codes go to Stock.
        """
        rows = [
            create_test_row(
                "Product L", "Size M", stock=0,
                store_quantities={
                    "125004 EKT-PC-Гринвич": 5,  # Would be paired, but pairs not configured
                    "125005 EKT-PC-Мега": 0,
                }
            )
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config)  # config without pairs
        previews = balancer.preview(df, header_row=7)

        assert len(previews) == 1
        preview = previews[0]

        # All excess to Stock (no pairs configured)
        assert preview.total_quantity == 3
        assert len(preview.transfers) == 1
        assert preview.transfers[0].receiver == "Сток"
