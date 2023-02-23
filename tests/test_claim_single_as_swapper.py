import unittest

from base_test_case import BaseTestCase
from app_client import AppClient


class TestClaimSingleAsSwapper(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.creator = self.create_account(initial_funding=10_000_000)
        self.app_client = AppClient(self.algod_client)
        self.app_id = self.app_client.create_app(self.creator)
        self.user = self.create_account(initial_funding=10_000_000)
        self.referrer = self.create_account(initial_funding=10_000_000)
        self.swapper = self.create_account(initial_funding=10_000_000)
        self.beneficiary = self.create_account(initial_funding=10_000_000)
        self.escrow = self.app_client.escrow_logicsig(self.referrer.pk, self.app_id)
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
                self.escrow.address(),
                [asset_id]
        ).execute(self.algod_client, 1000)


    def test_claim_algo_as_swapper(self):
        target_asset_id = self.create_asset(self.creator)
        # fund the escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # configure the swapper
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper.pk,
        ).execute(self.algod_client, 1000)
        # grant permission to swapper
        self.opt_escrow_into_asset(target_asset_id)
        self.app_client.prepare_enable_swapping(
                self.referrer,
                self.app_id,
                self.escrow.address(),
                target_asset_id,
        ).execute(self.algod_client, 1000)
        # claim algo as swapper
        holdings1 = self.get_asset_holding(self.beneficiary.pk, asset_id)
        result = self.app_client.prepare_claim_single(
                self.swapper,
                self.app_id,
                self.escrow.address(),
                asset_id,
                5000,
                close_out=0,
                beneficiary_address=self.beneficiary.pk,
        ).execute(self.algod_client, 1000)
        holdings2 = self.get_asset_holding(self.beneficiary.pk, asset_id)
        self.assertEqual(5000, result.abi_results[0].return_value)


    def test_claim_algo_as_swapper_without_being_given_permission_fails(self):
        # fund the escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # configure the swapper
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper.pk,
        ).execute(self.algod_client, 1000)
        # claim algo as swapper without being given permission fails
        with self.assertRaises(Exception):
            self.app_client.prepare_claim_single(
                    self.swapper,
                    self.app_id,
                    self.escrow.address(),
                    asset_id,
                    5000,
                    close_out=0,
                    beneficiary_address=self.beneficiary.pk,
            ).execute(self.algod_client, 1000)


    def test_claim_algo_as_swapper_after_revoking_permission_fails(self):
        target_asset_id = self.create_asset(self.creator)
        # fund the escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # configure the swapper
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper.pk,
        ).execute(self.algod_client, 1000)
        # grant permission to swapper
        self.opt_escrow_into_asset(target_asset_id)
        self.app_client.prepare_enable_swapping(
                self.referrer,
                self.app_id,
                self.escrow.address(),
                target_asset_id,
        ).execute(self.algod_client, 1000)
        # revoke permission from swapper again
        self.app_client.prepare_disable_swapping(
                self.referrer,
                self.app_id,
                self.escrow.address(),
        ).execute(self.algod_client, 1000)
        # claim algo as swapper without being given permission fails
        with self.assertRaises(Exception):
            self.app_client.prepare_claim_single(
                    self.swapper,
                    self.app_id,
                    self.escrow.address(),
                    asset_id,
                    5000,
                    close_out=0,
                    beneficiary_address=self.beneficiary.pk,
            ).execute(self.algod_client, 1000)


    def test_claim_algo_as_referrer_still_works_after_giving_permission_to_swapper(self):
        target_asset_id = self.create_asset(self.creator)
        # fund the escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # configure the swapper
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper.pk,
        ).execute(self.algod_client, 1000)
        # grant permission to swapper
        self.opt_escrow_into_asset(target_asset_id)
        self.app_client.prepare_enable_swapping(
                self.referrer,
                self.app_id,
                self.escrow.address(),
                target_asset_id,
        ).execute(self.algod_client, 1000)
        # claim algo as referrer
        holdings1 = self.get_asset_holding(self.beneficiary.pk, asset_id)
        result = self.app_client.prepare_claim_single(
                self.referrer,
                self.app_id,
                self.escrow.address(),
                asset_id,
                5000,
                close_out=0,
                beneficiary_address=self.beneficiary.pk,
        ).execute(self.algod_client, 1000)
        holdings2 = self.get_asset_holding(self.beneficiary.pk, asset_id)
        self.assertEqual(5000, result.abi_results[0].return_value)


    def test_claim_algo_as_non_swapper_and_non_referrer_fails(self):
        target_asset_id = self.create_asset(self.creator)
        self.attacker = self.create_account(initial_funding=10_000_000)
        # fund the escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # configure the swapper
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper.pk,
        ).execute(self.algod_client, 1000)
        # grant permission to swapper
        self.opt_escrow_into_asset(target_asset_id)
        self.app_client.prepare_enable_swapping(
                self.referrer,
                self.app_id,
                self.escrow.address(),
                target_asset_id,
        ).execute(self.algod_client, 1000)
        # claim algo as attacker fails
        with self.assertRaises(Exception):
            self.app_client.prepare_claim_single(
                    self.attacker,
                    self.app_id,
                    self.escrow.address(),
                    asset_id,
                    5000,
                    close_out=0,
                    beneficiary_address=self.beneficiary.pk,
            ).execute(self.algod_client, 1000)


    def test_claim_algo_only_last_swapper_can_claim(self):
        target_asset_id = self.create_asset(self.creator)
        self.swapper1 = self.create_account(initial_funding=10_000_000)
        self.swapper2 = self.create_account(initial_funding=10_000_000)
        # fund the escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # grant permission to swapper
        self.opt_escrow_into_asset(target_asset_id)
        self.app_client.prepare_enable_swapping(
                self.referrer,
                self.app_id,
                self.escrow.address(),
                target_asset_id,
        ).execute(self.algod_client, 1000)
        # configure the swapper
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper1.pk,
        ).execute(self.algod_client, 1000)
        # claim algo as swapper1 works
        holdings1 = self.get_asset_holding(self.beneficiary.pk, asset_id)
        result = self.app_client.prepare_claim_single(
                self.swapper1,
                self.app_id,
                self.escrow.address(),
                asset_id,
                1000,
                close_out=0,
                beneficiary_address=self.beneficiary.pk,
        ).execute(self.algod_client, 1000)
        holdings2 = self.get_asset_holding(self.beneficiary.pk, asset_id)
        self.assertEqual(1000, result.abi_results[0].return_value)
        # re-configure the swapper
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper2.pk,
        ).execute(self.algod_client, 1000)
        # now only swapper2 can claim
        holdings1 = self.get_asset_holding(self.beneficiary.pk, asset_id)
        result = self.app_client.prepare_claim_single(
                self.swapper2,
                self.app_id,
                self.escrow.address(),
                asset_id,
                2000,
                close_out=0,
                beneficiary_address=self.beneficiary.pk,
        ).execute(self.algod_client, 2000)
        holdings2 = self.get_asset_holding(self.beneficiary.pk, asset_id)
        # the first swapper cannot claim anymore
        with self.assertRaises(Exception):
            self.app_client.prepare_claim_single(
                    self.swapper1,
                    self.app_id,
                    self.escrow.address(),
                    asset_id,
                    500,
                    close_out=0,
                    beneficiary_address=self.beneficiary.pk,
            ).execute(self.algod_client, 1000)


    def test_swapper_cannot_claim_target_asset(self):
        target_asset_id = 0
        # fund the escrow
        asset_id = 0 # ALGO
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # configure the swapper
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper.pk,
        ).execute(self.algod_client, 1000)
        # grant permission to swapper
        self.opt_escrow_into_asset(target_asset_id)
        self.app_client.prepare_enable_swapping(
                self.referrer,
                self.app_id,
                self.escrow.address(),
                target_asset_id,
        ).execute(self.algod_client, 1000)
        # claim algo as swapper
        with self.assertRaises(Exception):
            self.app_client.prepare_claim_single(
                    self.swapper,
                    self.app_id,
                    self.escrow.address(),
                    asset_id,
                    5000,
                    close_out=0,
                    beneficiary_address=self.beneficiary.pk,
            ).execute(self.algod_client, 1000)


    def test_swapper_cannot_claim_target_asa(self):
        target_asset_id = self.create_asset(self.creator)
        # fund the escrow
        asset_id = target_asset_id
        self.opt_escrow_into_asset(target_asset_id)
        self.send_asset(self.creator, self.escrow.address(), asset_id, 5000)
        # configure the swapper
        self.app_client.prepare_set_swapper_address(
                self.creator,
                self.app_id,
                self.swapper.pk,
        ).execute(self.algod_client, 1000)
        # grant permission to swapper
        self.app_client.prepare_enable_swapping(
                self.referrer,
                self.app_id,
                self.escrow.address(),
                target_asset_id,
        ).execute(self.algod_client, 1000)
        # claim algo as swapper
        with self.assertRaises(Exception):
            self.app_client.prepare_claim_single(
                    self.swapper,
                    self.app_id,
                    self.escrow.address(),
                    asset_id,
                    5000,
                    close_out=0,
                    beneficiary_address=self.beneficiary.pk,
            ).execute(self.algod_client, 1000)

if __name__ == "__main__":
    unittest.main()
