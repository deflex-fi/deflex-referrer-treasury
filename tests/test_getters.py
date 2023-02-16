import unittest

from base_test_case import BaseTestCase
from app_client import AppClient


class TestGetters(BaseTestCase):

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


    def test_get_escrow_by_referrer(self):
        response = self.app_client.prepare_get_escrow_by_referrer(
                self.user,
                self.app_id,
                self.referrer.pk,
        ).execute(self.algod_client, 1000)
        self.assertEqual(self.escrow.pk, response.abi_results[0].return_value)


    def test_get_escrow_for_non_existing_referrer(self):
        response = self.app_client.prepare_get_escrow_by_referrer(
                self.user,
                self.app_id,
                self.user.pk,
        ).execute(self.algod_client, 1000)
        zero_address = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ'
        self.assertEqual(zero_address, response.abi_results[0].return_value)


    def test_get_referrer_by_escrow(self):
        response = self.app_client.prepare_get_referrer_by_escrow(
                self.user,
                self.app_id,
                self.escrow.pk,
        ).execute(self.algod_client, 1000)
        self.assertEqual(self.referrer.pk, response.abi_results[0].return_value)


    def test_get_referrer_for_non_existing_escrow(self):
        response = self.app_client.prepare_get_referrer_by_escrow(
                self.user,
                self.app_id,
                self.user.pk,
        ).execute(self.algod_client, 1000)
        zero_address = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ'
        self.assertEqual(zero_address, response.abi_results[0].return_value)


if __name__ == "__main__":
    unittest.main()
