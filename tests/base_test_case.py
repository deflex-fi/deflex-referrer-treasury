import base64
from typing import List
import unittest
import random

from algosdk.kmd import KMDClient
from algosdk import mnemonic
from algosdk.v2client import algod
from algosdk.v2client import indexer
from algosdk import account as acc
from algosdk import transaction

from app_client import AppClient
from keypair import KeyPair


class BaseTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.algod_client = cls.create_algod_client()


    @staticmethod
    def create_algod_client():
        algod_address = 'http://localhost:4001'
        algod_token   = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        return algod.AlgodClient(algod_token, algod_address)


    @staticmethod
    def get_genesis_accounts() -> List[KeyPair]:
        KMD_ADDRESS = "http://localhost:4002"
        KMD_TOKEN = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        KMD_WALLET_NAME = "unencrypted-default-wallet"
        KMD_WALLET_PASSWORD = ""

        kmd = KMDClient(KMD_TOKEN, KMD_ADDRESS)

        wallets = kmd.list_wallets()
        wallet_id = None
        for wallet in wallets:
            if wallet["name"] == KMD_WALLET_NAME:
                wallet_id = wallet["id"]
                break

        if wallet_id is None:
            raise Exception("Wallet not found: {}".format(KMD_WALLET_NAME))

        wallet_handle = kmd.init_wallet_handle(wallet_id, KMD_WALLET_PASSWORD)

        try:
            addresses = kmd.list_keys(wallet_handle)
            key_pairs = []
            for addr in addresses:
                sk = kmd.export_key(wallet_handle, KMD_WALLET_PASSWORD, addr)
                # key_pairs.append(KeyPair(addr, mnemonic.from_private_key(sk)))
                key_pairs.append(KeyPair(addr, sk))
            return key_pairs
        finally:
            kmd.release_wallet_handle(wallet_handle)


    def create_account(self, initial_funding: int = 1_000_000) -> KeyPair:
        private_key, address = acc.generate_account()
        account = KeyPair(address, private_key)
        if initial_funding > 0:
            creator = self.get_genesis_accounts()[0]
            txn = transaction.PaymentTxn(
                sender=creator.pk,
                sp=self.algod_client.suggested_params(),
                receiver=address,
                amt=initial_funding,
                note='',
            )
            txn = txn.sign(creator.sk)
            self.exec_txns([txn])
        return account


    def exec_txns(self, signed_txns: list):
        tx_id = signed_txns[0].transaction.get_txid()
        self.algod_client.send_transactions(signed_txns)
        transaction.wait_for_confirmation(self.algod_client, tx_id, 10)
        transaction_response = self.algod_client.pending_transaction_info(tx_id)
        return transaction_response


    def create_asset(self, account: KeyPair, total: int = 2**64-1, decimals: int = 6):
        seed = random.randint(1, 2**16)
        txn = transaction.AssetCreateTxn(
                sender=account.pk,
                total=total,
                decimals=decimals,
                default_frozen=False,
                manager=account.pk,
                reserve=account.pk,
                freeze=account.pk,
                clawback=account.pk,
                unit_name=f"D{seed}",
                asset_name=f"Dummy {seed}",
                url=f"https://dummy.asset/{seed}",
                note='',
                sp=self.algod_client.suggested_params(),
        )
        txn = txn.sign(account.sk)
        response = self.exec_txns([txn])
        return response['asset-index']


    def opt_account_into_asset(self, account: KeyPair, asset_id: int):
        if asset_id == 0:
            return
        txn = transaction.AssetOptInTxn(
            sender=account.pk,
            sp=self.algod_client.suggested_params(),
            index=asset_id,
            note='',
        )
        txn = txn.sign(account.sk)
        self.exec_txns([txn])


    def send_asset(self, sender: KeyPair, receiver: str, asset_id: int, amount: int):
        if asset_id == 0:
            txn = transaction.PaymentTxn(
                sender=sender.pk,
                sp=self.algod_client.suggested_params(),
                receiver=receiver,
                amt=amount,
                note='',
            ).sign(sender.sk)
            self.exec_txns([txn])
        else:
            txn = transaction.AssetTransferTxn(
                sender=sender.pk,
                sp=self.algod_client.suggested_params(),
                receiver=receiver,
                amt=amount,
                index=asset_id,
                note='',
            ).sign(sender.sk)
            self.exec_txns([txn])


    def get_asset_holding(self, address: str, asset_id: int):
        data = self.algod_client.account_info(address)
        if asset_id == 0:
            return data['amount']
        else:
            for asset in data['assets']:
                if asset['asset-id'] == asset_id:
                    return asset['amount']
        raise Exception('could not find holdings for asset {}'.format(asset_id))


if __name__ == "__main__":
    unittest.main()
