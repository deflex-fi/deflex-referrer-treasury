import unittest

from base_test_case import BaseTestCase
from app_client import AppClient


class TestOptEscrowIntoAssets(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.creator = self.create_account(initial_funding=10_000_000)
        self.app_client = AppClient(self.algod_client)
        self.app_id = self.app_client.create_app(self.creator)
        self.user = self.create_account(initial_funding=10_000_000)
        self.referrer = self.create_account(initial_funding=10_000_000)
        self.escrow = self.app_client.escrow_logicsig(self.referrer.pk, self.app_id)
        self.app_client.prepare_register_escrow(
                self.user,
                self.app_id,
                self.referrer.pk,
                self.escrow,
        ).execute(self.algod_client, 1000)


    def test_opt_into_zero_assets(self):
        self.app_client.prepare_opt_into_assets(
                self.user,
                self.app_id,
                self.escrow.address(),
                []
        ).execute(self.algod_client, 1000)


    def test_opt_into_one_asset(self):
        asset_id = self.create_asset(self.creator)
        self.app_client.prepare_opt_into_assets(
                self.user,
                self.app_id,
                self.escrow.address(),
                [asset_id]
        ).execute(self.algod_client, 1000)
        self.send_asset(self.creator, self.escrow.address(), asset_id, 123)


    def test_opt_into_multiple_assets(self):
        asset1_id = self.create_asset(self.creator)
        asset2_id = self.create_asset(self.creator)
        asset3_id = self.create_asset(self.creator)
        self.app_client.prepare_opt_into_assets(
                self.user,
                self.app_id,
                self.escrow.address(),
                [asset1_id, asset2_id, asset3_id]
        ).execute(self.algod_client, 1000)
        # test that we can send assets to the escrow
        self.send_asset(self.creator, self.escrow.address(), asset1_id, 123)
        self.send_asset(self.creator, self.escrow.address(), asset2_id, 456)
        self.send_asset(self.creator, self.escrow.address(), asset3_id, 789)


    def test_opt_into_the_same_asset_twice(self):
        asset_id = self.create_asset(self.creator)
        self.app_client.prepare_opt_into_assets(
                self.user,
                self.app_id,
                self.escrow.address(),
                [asset_id]
        ).execute(self.algod_client, 1000)
        # opting in again doesn't do anything
        self.app_client.prepare_opt_into_assets(
                self.user,
                self.app_id,
                self.escrow.address(),
                [asset_id]
        ).execute(self.algod_client, 1000)


if __name__ == "__main__":
    unittest.main()
