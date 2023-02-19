import unittest

from base_test_case import BaseTestCase
from app_client import AppClient

class EscrowTemplateGenerator(BaseTestCase):

    def generate(self):
        BaseTestCase.setUpClass()
        self.app_client = AppClient(self.algod_client)
        print(self.app_client.escrow_template())


if __name__ == "__main__":
    EscrowTemplateGenerator().generate()
