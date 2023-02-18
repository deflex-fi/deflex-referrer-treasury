import unittest

from base_test_case import BaseTestCase
from app_client import AppClient


class TestRegisterEscrow(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.creator = self.create_account(initial_funding=10_000_000)
        self.app_client = AppClient(self.algod_client)
        self.app_id = self.app_client.create_app(self.creator)


    def test_register_escrow(self):
        user = self.create_account(initial_funding=10_000_000)
        referrer = self.create_account(initial_funding=10_000_000)
        composer = self.app_client.prepare_register_escrow(
                user,
                self.app_id,
                referrer.pk,
        )
        composer.execute(self.algod_client, 1000)


    def test_register_same_escrow_for_same_referrer_twice_fails(self):
        user = self.create_account(initial_funding=10_000_000)
        referrer = self.create_account(initial_funding=10_000_000)
        # registering a referrer for the first time works
        self.app_client.prepare_register_escrow(
                user,
                self.app_id,
                referrer.pk,
                self.app_client.escrow_logicsig(referrer.pk, self.app_id),
        ).execute(self.algod_client, 1000)
        # and fails the second time
        with self.assertRaises(Exception):
            self.app_client.prepare_register_escrow(
                    user,
                    self.app_id,
                    referrer.pk,
                    self.app_client.escrow_logicsig(referrer.pk, self.app_id),
            ).execute(self.algod_client, 1000)


    def test_register_different_escrows_for_one_referrer_fails(self):
        user = self.create_account(initial_funding=10_000_000)
        referrer = self.create_account(initial_funding=10_000_000)
        # registering a referrer for the first time works
        self.app_client.prepare_register_escrow(
                user,
                self.app_id,
                referrer.pk,
                self.app_client.escrow_logicsig(referrer.pk, self.app_id),
        ).execute(self.algod_client, 1000)
        # and fails the second time
        with self.assertRaises(Exception):
            self.app_client.prepare_register_escrow(
                    user,
                    self.app_id,
                    referrer.pk,
                    self.app_client.escrow_logicsig(user.pk, self.app_id),
            ).execute(self.algod_client, 1000)


    def test_register_same_escrow_for_two_different_referrer_fails(self):
        user1 = self.create_account(initial_funding=10_000_000)
        user2 = self.create_account(initial_funding=10_000_000)
        referrer1 = self.create_account(initial_funding=10_000_000)
        referrer2 = self.create_account(initial_funding=10_000_000)
        escrow = self.app_client.escrow_logicsig(referrer1.pk, self.app_id)
        # registering escrow for the first time works
        self.app_client.prepare_register_escrow(
                user1,
                self.app_id,
                referrer1.pk,
                escrow,
        ).execute(self.algod_client, 1000)
        # and fails the second time because escrow is rekeyed
        with self.assertRaises(Exception):
            self.app_client.prepare_register_escrow(
                    user2,
                    self.app_id,
                    referrer2.pk,
                    escrow,
            ).execute(self.algod_client, 1000)


if __name__ == "__main__":
    unittest.main()
