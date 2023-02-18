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
        self.escrow = self.app_client.escrow_logicsig(self.referrer.pk, self.app_id)
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
        self.assertEqual(self.escrow.address(), response.abi_results[0].return_value)


    def test_get_escrow_for_non_existing_referrer(self):
        response = self.app_client.prepare_get_escrow_by_referrer(
                self.user,
                self.app_id,
                self.user.pk,
        ).execute(self.algod_client, 1000)
        expected_escrow = self.app_client.escrow_address(self.user.pk, self.app_id)
        self.assertEqual(expected_escrow, response.abi_results[0].return_value)


if __name__ == "__main__":
    unittest.main()
