import unittest

from base_test_case import BaseTestCase
from app_client import AppClient


class TestSwapperAddress(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.creator = self.create_account(initial_funding=10_000_000)
        self.app_client = AppClient(self.algod_client)
        self.app_id = self.app_client.create_app(self.creator)
        self.user = self.create_account(initial_funding=10_000_000)
        self.swapper = self.create_account(initial_funding=10_000_000)


    def test_swapper_address(self):
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper.pk,
        ).execute(self.algod_client, 1000)


    def test_swapper_address_as_non_creator_fails(self):
        with self.assertRaises(Exception):
            self.app_client.prepare_set_swapper_address(
                    self.user,
                    self.app_id,
                    self.swapper.pk,
            ).execute(self.algod_client, 1000)


if __name__ == "__main__":
    unittest.main()
