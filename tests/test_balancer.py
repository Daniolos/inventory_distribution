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


class TestMinimumSizesRuleInBalancing:
    """Tests for minimum sizes rule applied to paired store balancing.

    Rule: When paired store wants to send to partner:
    - If partner has 0-1 sizes of this product AND product has 4+ sizes total
    - Only transfer if 3+ sizes can be transferred (all-or-nothing)
    - If <3 sizes available from sender -> send everything to Stock instead
    """

    def test_partner_0_sizes_sender_3plus_transfers_all(self, config_with_pairs):
        """Partner has 0 sizes, sender can provide 3+ sizes -> all transfer to partner.

        Product has 4 sizes, 125004 has excess in all 4, 125005 has 0.
        -> All 4 sizes should transfer to partner (each 1 item).
        """
        rows = [
            create_test_row("Product A", "Size S", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product A", "Size M", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product A", "Size L", store_quantities={
                "125004 EKT-PC-Гринвич": 3, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product A", "Size XL", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        # Partner should receive all 4 sizes (1 of each)
        transfers_to_partner = []
        for preview in previews:
            for transfer in preview.transfers:
                if "125005" in transfer.receiver:
                    transfers_to_partner.append(transfer)

        assert len(transfers_to_partner) == 4

    def test_partner_0_sizes_sender_only_2_all_to_stock(self, config_with_pairs):
        """Partner has 0 sizes, sender can only provide 2 sizes -> all to Stock.

        Product has 4 sizes, but 125004 has excess in only 2 sizes.
        -> Nothing to partner (min 3 required), all to Stock.
        """
        rows = [
            create_test_row("Product B", "Size S", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product B", "Size M", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
            # These sizes don't have excess (at or below threshold)
            create_test_row("Product B", "Size L", store_quantities={
                "125004 EKT-PC-Гринвич": 2, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product B", "Size XL", store_quantities={
                "125004 EKT-PC-Гринвич": 1, "125005 EKT-PC-Мега": 0
            }),
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        # No transfers to partner (only 2 sizes with excess)
        transfers_to_partner = []
        transfers_to_stock = []
        for preview in previews:
            for transfer in preview.transfers:
                if "125005" in transfer.receiver:
                    transfers_to_partner.append(transfer)
                elif transfer.receiver == "Сток":
                    transfers_to_stock.append(transfer)

        assert len(transfers_to_partner) == 0
        # All excess goes to Stock: (5-2) + (4-2) = 3 + 2 = 5
        total_to_stock = sum(t.quantity for t in transfers_to_stock)
        assert total_to_stock == 5

    def test_partner_2_sizes_normal_rule_applies(self, config_with_pairs):
        """Partner already has 2 sizes -> minimum sizes rule doesn't apply.

        125005 has 2 sizes, so normal rule applies (1 item per empty variant).
        """
        rows = [
            create_test_row("Product C", "Size S", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 1
            }),
            create_test_row("Product C", "Size M", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 1
            }),
            create_test_row("Product C", "Size L", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product C", "Size XL", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        # Partner has 2 sizes already, normal rule applies
        # Partner receives Size L and Size XL (those with 0 inventory)
        transfers_to_partner = []
        for preview in previews:
            for transfer in preview.transfers:
                if "125005" in transfer.receiver:
                    transfers_to_partner.append(transfer)

        # Should receive 2 sizes (L and XL where partner has 0)
        assert len(transfers_to_partner) == 2

    def test_product_less_than_4_sizes_no_min_rule(self, config_with_pairs):
        """Product has <4 sizes -> minimum sizes rule doesn't apply.

        Product has only 3 sizes, so standard balancing applies.
        """
        rows = [
            create_test_row("Product D", "Size S", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product D", "Size M", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product D", "Size L", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        # Product has <4 sizes, standard rule applies
        # Partner receives 1 item per size (normal behavior)
        transfers_to_partner = []
        for preview in previews:
            for transfer in preview.transfers:
                if "125005" in transfer.receiver:
                    transfers_to_partner.append(transfer)

        # All 3 sizes should transfer (min rule doesn't apply for <4 sizes)
        assert len(transfers_to_partner) == 3

    def test_partner_has_1_size_sender_3plus_transfers(self, config_with_pairs):
        """Partner has 1 size, sender can provide 3+ sizes -> transfers happen.

        Partner has 1 size (< MIN_SIZES_THRESHOLD=2), so min rule applies.
        Sender has 3+ sizes with excess -> all transfer.
        """
        rows = [
            create_test_row("Product E", "Size S", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 1  # Partner has this
            }),
            create_test_row("Product E", "Size M", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product E", "Size L", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product E", "Size XL", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        # Partner has 1 size, min rule applies
        # Sender has 3 sizes with excess where partner has 0 -> transfers happen
        transfers_to_partner = []
        for preview in previews:
            for transfer in preview.transfers:
                if "125005" in transfer.receiver:
                    transfers_to_partner.append(transfer)

        # Partner receives 3 sizes (M, L, XL - those where partner has 0)
        assert len(transfers_to_partner) == 3


class TestBalancerIndicatorFlags:
    """Tests for indicator flags (skip_reason, min_sizes_skipped, etc.)."""

    def test_min_sizes_skipped_flag_set_when_partner_blocked(self, config_with_pairs):
        """When partner is blocked due to min sizes rule, flag should be set.

        Product has 4 sizes, sender has only 2 with excess -> partner blocked.
        """
        rows = [
            create_test_row("Product X", "Size S", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product X", "Size M", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product X", "Size L", store_quantities={
                "125004 EKT-PC-Гринвич": 2, "125005 EKT-PC-Мега": 0  # No excess
            }),
            create_test_row("Product X", "Size XL", store_quantities={
                "125004 EKT-PC-Гринвич": 1, "125005 EKT-PC-Мега": 0  # No excess
            }),
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        # Check that min_sizes_skipped is True for rows with excess
        for preview in previews:
            if preview.has_transfers:
                assert preview.min_sizes_skipped is True
                assert preview.skip_reason is not None
                assert "125005" in preview.skip_reason

    def test_uses_standard_distribution_flag_for_small_products(self, config_with_pairs):
        """Products with <4 sizes should have uses_standard_distribution flag."""
        rows = [
            create_test_row("Product Y", "Size S", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product Y", "Size M", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product Y", "Size L", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        # All rows should have uses_standard_distribution = True
        for preview in previews:
            assert preview.uses_standard_distribution is True

    def test_skipped_stores_contains_partner_when_blocked(self, config_with_pairs):
        """When partner is blocked, skipped_stores should contain the partner."""
        rows = [
            create_test_row("Product Z", "Size S", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product Z", "Size M", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product Z", "Size L", store_quantities={
                "125004 EKT-PC-Гринвич": 2, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product Z", "Size XL", store_quantities={
                "125004 EKT-PC-Гринвич": 1, "125005 EKT-PC-Мега": 0
            }),
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        # Check skipped_stores on rows with transfers
        for preview in previews:
            if preview.has_transfers:
                assert len(preview.skipped_stores) > 0
                partner_skipped = any(
                    "125005" in s.store_name for s in preview.skipped_stores
                )
                assert partner_skipped
                # Reason should be min_sizes
                assert preview.skipped_stores[0].reason == "min_sizes"

    def test_no_flags_when_transfer_succeeds(self, config_with_pairs):
        """When transfer to partner succeeds, no skip flags should be set."""
        rows = [
            create_test_row("Product W", "Size S", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product W", "Size M", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product W", "Size L", store_quantities={
                "125004 EKT-PC-Гринвич": 5, "125005 EKT-PC-Мега": 0
            }),
            create_test_row("Product W", "Size XL", store_quantities={
                "125004 EKT-PC-Гринвич": 4, "125005 EKT-PC-Мега": 0
            }),
        ]
        df = create_test_df(rows)

        balancer = InventoryBalancer(config_with_pairs)
        previews = balancer.preview(df, header_row=7)

        # All 4 sizes should transfer to partner - no skip flags
        for preview in previews:
            assert preview.min_sizes_skipped is False
            assert preview.skip_reason is None
            assert len(preview.skipped_stores) == 0
            # Product has 4 sizes, so uses_standard_distribution should be False
            assert preview.uses_standard_distribution is False
