import unittest

from base_test_case import BaseTestCase
from app_client import AppClient


class TestRegisterEscrow(BaseTestCase):

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
        # claim for the first time
        self.opt_account_into_asset(self.referrer, asset_id)
        result = self.app_client.prepare_claim(
                self.referrer,
                self.app_id,
                self.escrow.pk,
                asset_id,
                5000,
        ).execute(self.algod_client, 1000)
        self.assertEqual(5000, result.abi_results[0].return_value)


    def test_claim_asset(self):
        # opt into asset
        asset_id = self.create_asset(self.creator)
        self.opt_escrow_into_asset(asset_id)
        self.send_asset(self.creator, self.escrow.pk, asset_id, 123)
        # claim for the first time
        self.opt_account_into_asset(self.referrer, asset_id)
        holdings1 = self.get_asset_holding(self.referrer.pk, asset_id)
        result = self.app_client.prepare_claim(
                self.referrer,
                self.app_id,
                self.escrow.pk,
                asset_id,
                9,
        ).execute(self.algod_client, 1000)
        holdings2 = self.get_asset_holding(self.referrer.pk, asset_id)
        self.assertEqual(9, result.abi_results[0].return_value)
        self.assertEqual(9, holdings2 - holdings1)
        # claim rest for the second time
        holdings1 = self.get_asset_holding(self.referrer.pk, asset_id)
        result = self.app_client.prepare_claim(
                self.referrer,
                self.app_id,
                self.escrow.pk,
                asset_id,
                0,
        ).execute(self.algod_client, 1000)
        holdings2 = self.get_asset_holding(self.referrer.pk, asset_id)
        self.assertEqual(123-9, result.abi_results[0].return_value)
        self.assertEqual(123-9, holdings2 - holdings1)


    def test_claim_asset_with_different_beneficiary(self):
        beneficiary = self.create_account(initial_funding=10_000_000)
        # opt into asset
        asset_id = self.create_asset(self.creator)
        self.opt_escrow_into_asset(asset_id)
        self.send_asset(self.creator, self.escrow.pk, asset_id, 123)
        # claim for the first time
        self.opt_account_into_asset(beneficiary, asset_id)
        holdings1 = self.get_asset_holding(beneficiary.pk, asset_id)
        result = self.app_client.prepare_claim(
                self.referrer,
                self.app_id,
                self.escrow.pk,
                asset_id,
                9,
                beneficiary.pk,
        ).execute(self.algod_client, 1000)
        holdings2 = self.get_asset_holding(beneficiary.pk, asset_id)
        self.assertEqual(9, result.abi_results[0].return_value)
        self.assertEqual(9, holdings2 - holdings1)


    def test_claim_more_algo_than_owned_fails(self):
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.pk, asset_id, 92384)
        with self.assertRaises(Exception):
            self.app_client.prepare_claim(
                    self.referrer,
                    self.app_id,
                    self.escrow.pk,
                    asset_id,
                    92385,
            ).execute(self.algod_client, 1000)


    def test_claim_more_of_asset_than_owned_fails(self):
        # opt into asset
        asset_id = self.create_asset(self.creator)
        self.opt_escrow_into_asset(asset_id)
        self.send_asset(self.creator, self.escrow.pk, asset_id, 123)
        # claim for the first time
        self.opt_account_into_asset(self.referrer, asset_id)
        with self.assertRaises(Exception):
            self.app_client.prepare_claim(
                    self.referrer,
                    self.app_id,
                    self.escrow.pk,
                    asset_id,
                    150,
            ).execute(self.algod_client, 1000)


    def test_claim_algo_from_someone_elses_escrow(self):
        # set up second escrow account for a second referrer, and fund it
        self.referrer2 = self.create_account(initial_funding=10_000_000)
        self.escrow2 = self.create_account(initial_funding=0)
        self.app_client.prepare_register_escrow(
                self.user,
                self.app_id,
                self.referrer2.pk,
                self.escrow2,
        ).execute(self.algod_client, 1000)
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow2.pk, asset_id, 5000)
        # now try to claim from first referrer
        with self.assertRaises(Exception):
            self.app_client.prepare_claim(
                    self.referrer,
                    self.app_id,
                    self.escrow2.pk,
                    asset_id,
                    150,
            ).execute(self.algod_client, 1000)


if __name__ == "__main__":
    unittest.main()
