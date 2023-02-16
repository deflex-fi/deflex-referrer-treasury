import unittest

from base_test_case import BaseTestCase
from app_client import AppClient


class TestClaim(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.creator = self.create_account(initial_funding=10_000_000)
        self.app_client = AppClient(self.algod_client)
        self.app_id = self.app_client.create_app(self.creator)
        self.user = self.create_account(initial_funding=10_000_000)
        self.referrer = self.create_account(initial_funding=10_000_000)
        self.escrow = self.create_account(initial_funding=0)
        self.app_client.prepare_register_escrow(
                self.user,
                self.app_id,
                self.referrer.pk,
                self.escrow,
        ).execute(self.algod_client, 1000)


    def opt_escrow_into_asset(self, asset_id):
        self.app_client.prepare_opt_into_assets(
                self.user,
                self.app_id,
                self.escrow.pk,
                [asset_id]
        ).execute(self.algod_client, 1000)


    def test_claim_algo(self):
        # opt into asset
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.pk, asset_id, 5000)
        # claim ALGO
        holdings1 = self.get_asset_holding(self.referrer.pk, asset_id)
        result = self.app_client.prepare_claim(
                self.user,
                self.app_id,
                self.referrer.pk,
                self.escrow.pk,
                [asset_id],
        ).execute(self.algod_client, 1000)
        holdings2 = self.get_asset_holding(self.referrer.pk, asset_id)
        self.assertEqual(5000, holdings2 - holdings1)


    def test_claim_asset(self):
        # opt into asset
        asset_id = self.create_asset(self.creator)
        self.opt_escrow_into_asset(asset_id)
        self.send_asset(self.creator, self.escrow.pk, asset_id, 123)
        # claim asset
        self.opt_account_into_asset(self.referrer, asset_id)
        holdings1 = self.get_asset_holding(self.referrer.pk, asset_id)
        result = self.app_client.prepare_claim(
                self.user,
                self.app_id,
                self.referrer.pk,
                self.escrow.pk,
                [asset_id],
        ).execute(self.algod_client, 1000)
        holdings2 = self.get_asset_holding(self.referrer.pk, asset_id)
        self.assertEqual(123, holdings2 - holdings1)


    def test_claim_multiple_assets(self):
        # create assets and do necessary opt-ins
        asset0_id = 0 # ALGO
        asset1_id = self.create_asset(self.creator)
        asset2_id = self.create_asset(self.creator)
        asset3_id = self.create_asset(self.creator)
        self.opt_escrow_into_asset(asset1_id)
        self.opt_escrow_into_asset(asset2_id)
        self.opt_escrow_into_asset(asset3_id)
        self.opt_account_into_asset(self.referrer, asset0_id)
        self.opt_account_into_asset(self.referrer, asset1_id)
        self.opt_account_into_asset(self.referrer, asset2_id)
        self.opt_account_into_asset(self.referrer, asset3_id)
        self.send_asset(self.creator, self.escrow.pk, asset0_id, 1000000)
        self.send_asset(self.creator, self.escrow.pk, asset1_id, 100)
        self.send_asset(self.creator, self.escrow.pk, asset2_id, 200)
        self.send_asset(self.creator, self.escrow.pk, asset3_id, 300)
        # claim assets
        holdings10 = self.get_asset_holding(self.referrer.pk, asset0_id)
        holdings11 = self.get_asset_holding(self.referrer.pk, asset1_id)
        holdings12 = self.get_asset_holding(self.referrer.pk, asset2_id)
        holdings13 = self.get_asset_holding(self.referrer.pk, asset3_id)
        result = self.app_client.prepare_claim(
                self.user,
                self.app_id,
                self.referrer.pk,
                self.escrow.pk,
                [asset0_id, asset1_id, asset2_id, asset3_id],
        ).execute(self.algod_client, 1000)
        holdings20 = self.get_asset_holding(self.referrer.pk, asset0_id)
        holdings21 = self.get_asset_holding(self.referrer.pk, asset1_id)
        holdings22 = self.get_asset_holding(self.referrer.pk, asset2_id)
        holdings23 = self.get_asset_holding(self.referrer.pk, asset3_id)
        self.assertEqual(1000000, holdings20 - holdings10)
        self.assertEqual(100, holdings21 - holdings11)
        self.assertEqual(200, holdings22 - holdings12)
        self.assertEqual(300, holdings23 - holdings13)


    def test_claim_same_asset_multiple_times(self):
        # opt into asset
        asset_id = self.create_asset(self.creator)
        self.opt_escrow_into_asset(asset_id)
        self.send_asset(self.creator, self.escrow.pk, asset_id, 123)
        # claim asset
        self.opt_account_into_asset(self.referrer, asset_id)
        holdings1 = self.get_asset_holding(self.referrer.pk, asset_id)
        result = self.app_client.prepare_claim(
                self.user,
                self.app_id,
                self.referrer.pk,
                self.escrow.pk,
                [asset_id, asset_id, asset_id, asset_id],
        ).execute(self.algod_client, 1000)
        holdings2 = self.get_asset_holding(self.referrer.pk, asset_id)
        self.assertEqual(123, holdings2 - holdings1)


    def test_claim_asset_to_wrong_referrer_fails(self):
        # opt into asset
        asset_id = self.create_asset(self.creator)
        self.opt_escrow_into_asset(asset_id)
        self.send_asset(self.creator, self.escrow.pk, asset_id, 123)
        # claim asset
        self.opt_account_into_asset(self.referrer, asset_id)
        self.opt_account_into_asset(self.user, asset_id)
        with self.assertRaises(Exception):
            referrer_address = self.user.pk
            self.app_client.prepare_claim(
                    self.user,
                    self.app_id,
                    referrer_address,
                    self.escrow.pk,
                    [asset_id],
            ).execute(self.algod_client, 1000)


    def test_claim_algo_from_someone_elses_escrow_fails(self):
        # set up second escrow account for a second referrer, and fund it
        self.referrer2 = self.create_account(initial_funding=10_000_000)
        self.escrow2 = self.create_account(initial_funding=0)
        self.app_client.prepare_register_escrow(
                self.user,
                self.app_id,
                self.referrer2.pk,
                self.escrow2,
        ).execute(self.algod_client, 1000)
        # send some ALGO to second escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow2.pk, asset_id, 5000)
        # now try to claim from second escrow for first referrer
        with self.assertRaises(Exception):
            self.app_client.prepare_claim(
                    self.user,
                    self.app_id,
                    self.referrer.pk,
                    self.escrow2.pk,
                    [asset_id],
            ).execute(self.algod_client, 1000)


if __name__ == "__main__":
    unittest.main()
