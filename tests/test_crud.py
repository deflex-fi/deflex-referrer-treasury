import unittest

from base_test_case import BaseTestCase
from app_client import AppClient


class TestCrud(BaseTestCase):
    """
    Test CRUD (create, read, update, delete) operations on the app. Read is not
    relevant and ignored, but we test that creating the app is possible, while
    deleting and updating the app is disallowed.
    """

    def setUp(self):
        super().setUp()
        self.creator = self.create_account(initial_funding=10_000_000)
        self.app_client = AppClient(self.algod_client)


    def test_create(self):
        self.app_id = self.app_client.create_app(self.creator)


    def test_delete_rejected(self):
        self.app_id = self.app_client.create_app(self.creator)
        composer = self.app_client.prepare_delete(self.creator, self.app_id)
        with self.assertRaises(Exception):
            composer.execute(self.algod_client, 1000)


    def test_update_rejected(self):
        self.app_id = self.app_client.create_app(self.creator)
        composer = self.app_client.prepare_update(
                self.creator,
                self.app_id,
                self.app_client.approval_bytecode,
                self.app_client.clearstate_bytecode,
        )
        with self.assertRaises(Exception):
            composer.execute(self.algod_client, 1000)


if __name__ == "__main__":
    unittest.main()
