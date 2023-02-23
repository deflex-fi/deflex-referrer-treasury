import unittest

from base_test_case import BaseTestCase
from app_client import AppClient


class TestDisableSwapping(BaseTestCase):

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


    def test_disable_swapping(self):
        self.attacker = self.create_account(initial_funding=10_000_000)
        # fund the escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # disabling swapping
        self.app_client.prepare_disable_swapping(
                self.referrer,
                self.app_id,
                self.escrow.address(),
        ).execute(self.algod_client, 1000)


    def test_disable_swapping_as_non_referrer_fails(self):
        self.attacker = self.create_account(initial_funding=10_000_000)
        # fund the escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # disabling swapping fails since attacker is not referrer
        with self.assertRaises(Exception):
            self.app_client.prepare_disable_swapping(
                    self.attacker,
                    self.app_id,
                    self.escrow.address(),
            ).execute(self.algod_client, 1000)


if __name__ == "__main__":
    unittest.main()
