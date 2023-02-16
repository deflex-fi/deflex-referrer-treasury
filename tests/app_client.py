import tealish
import os
import base64
from typing import List, Optional

from algosdk.atomic_transaction_composer import AtomicTransactionComposer, AccountTransactionSigner, TransactionWithSigner
from algosdk.future.transaction import SuggestedParams
from algosdk.future import transaction
from algosdk.future.transaction import StateSchema
from algosdk.abi import Contract
from algosdk import encoding, account

from keypair import KeyPair


class AppClient:

    def __init__(self, algod_client):
        self.algod_client = algod_client
        basepath = os.path.dirname(os.path.realpath(__file__)) + "/../contracts/"
        with open(basepath + "treasury.approval.tl") as f:
            self.approval_tealish = f.read()
            self.approval_teal, _  = tealish.compile_program(self.approval_tealish)
            self.approval_teal = '\n'.join(self.approval_teal)
            self.approval_bytecode = self.compile_program(self.approval_teal)
        with open(basepath + "treasury.clearstate.tl") as f:
            self.clearstate_tealish = f.read()
            self.clearstate_teal, _  = tealish.compile_program(self.clearstate_tealish)
            self.clearstate_teal = '\n'.join(self.clearstate_teal)
            self.clearstate_bytecode = self.compile_program(self.clearstate_teal)
        self.contract = self._read_contract()


    def compile_program(self, source_code):
        compile_response = self.algod_client.compile(source_code)
        return base64.b64decode(compile_response['result'])


    def get_global_schema(self):
        global_ints  = 0
        global_bytes = 0
        return StateSchema(global_ints, global_bytes)


    def get_local_schema(self):
        local_ints  = 0
        local_bytes = 0
        return StateSchema(local_ints, local_bytes)


    def get_extra_pages(self):
        return 0


    def app_address(self, app_id: int) -> str:
        raw = b'appID'+(app_id).to_bytes(8, 'big')
        return encoding.encode_address(encoding.checksum(raw))


    def create_app(self, user: KeyPair):
        # create the app
        composer = self.prepare_create(user)
        composer.gather_signatures()
        composer.submit(self.algod_client)
        resp = transaction.wait_for_confirmation(
            self.algod_client, composer.tx_ids[0], 10
        )
        app_id = resp['application-index']
        # fund the app account
        composer, params = self._get_defaults()
        composer = composer.add_transaction(TransactionWithSigner(transaction.PaymentTxn(
            sender=user.pk,
            sp=params,
            receiver=self.app_address(app_id),
            amt=100000,
        ), AccountTransactionSigner(user.sk)))
        composer.execute(self.algod_client, 1000)
        return app_id


    def prepare_create(self,
            user: KeyPair,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        return composer.add_transaction(TransactionWithSigner(transaction.ApplicationCreateTxn(
            sender=user.pk,
            sp=params,
            on_complete=transaction.OnComplete.NoOpOC.real,
            approval_program=self.approval_bytecode,
            clear_program=self.clearstate_bytecode,
            global_schema=self.get_global_schema(),
            local_schema=self.get_local_schema(),
            extra_pages=self.get_extra_pages(),
        ), AccountTransactionSigner(user.sk)))


    def prepare_delete(self,
            user: KeyPair,
            app_id: int,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        return composer.add_transaction(TransactionWithSigner(transaction.ApplicationDeleteTxn(
            sender=user.pk,
            sp=params,
            index=app_id,
        ), AccountTransactionSigner(user.sk)))


    def prepare_update(self,
            user: KeyPair,
            app_id: int,
            approval_program,
            clearstate_program,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        return composer.add_transaction(TransactionWithSigner(transaction.ApplicationUpdateTxn(
            sender=user.pk,
            sp=params,
            index=app_id,
            approval_program=approval_program,
            clear_program=clearstate_program,
        ), AccountTransactionSigner(user.sk)))


    def prepare_test(self,
            user: KeyPair,
            app_id: int,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        return composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('sum'),
            sp=params,
            method_args=[
                1,
                2,
            ],
            signer=AccountTransactionSigner(user.sk),
        )


    def prepare_register_escrow(self,
            user: KeyPair,
            app_id: int,
            referrer_address: str,
            escrow: KeyPair = None,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        if escrow == None:
            escrow_key, escrow_address = account.generate_account()
            escrow = KeyPair(escrow_address, escrow_key)
        # fund escrow
        composer = composer.add_transaction(TransactionWithSigner(transaction.PaymentTxn(
            sender=user.pk,
            sp=params,
            receiver=escrow.pk,
            amt=157_000,
        ), AccountTransactionSigner(user.sk)))
        composer.txn_list[-1].txn.fee = 3000
        # call app
        composer.add_method_call(
            app_id=app_id,
            sender=escrow.pk,
            method=self.contract.get_method_by_name('Referrer_register_escrow'),
            sp=params,
            method_args=[
                referrer_address,
            ],
            boxes=[
                (app_id, bytes([0x00]) + encoding.decode_address(referrer_address)),
                (app_id, bytes([0x01]) + encoding.decode_address(escrow.pk)),
            ],
            rekey_to=self.app_address(app_id),
            signer=AccountTransactionSigner(escrow.sk),
        )
        composer.txn_list[-1].txn.fee = 0
        return composer


    def prepare_opt_into_assets(self,
            user: KeyPair,
            app_id: int,
            escrow_address: str,
            asset_ids: List[int],
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        # fund the MBR increase
        payment_txn = TransactionWithSigner(transaction.PaymentTxn(
            sender=user.pk,
            receiver=escrow_address,
            sp=params,
            amt=100_000 * len(asset_ids)
        ), AccountTransactionSigner(user.sk))
        payment_txn.txn.fee = 0
        # call the app
        composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('User_opt_into_assets'),
            sp=params,
            method_args=[
                payment_txn,
                escrow_address
            ],
            foreign_assets=asset_ids,
            signer=AccountTransactionSigner(user.sk),
        )
        composer.txn_list[-1].txn.fee = 2000 + 1000 * len(asset_ids)
        return composer


    def prepare_claim(self,
            user: KeyPair,
            app_id: int,
            escrow_address: str,
            asset_id: int,
            amount: int,
            beneficiary_address: str = None,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        if beneficiary_address == None:
            beneficiary_address = user.pk
        composer, params = self._get_defaults(composer, params)
        composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('Referrer_claim'),
            sp=params,
            method_args=[
                escrow_address,
                beneficiary_address,
                asset_id,
                amount,
            ],
            boxes=[
                (app_id, bytes([0x00]) + encoding.decode_address(user.pk)),
            ],
            signer=AccountTransactionSigner(user.sk),
        )
        composer.txn_list[-1].txn.fee = 2000
        return composer


    def prepare_get_escrow_by_referrer(self,
            user: KeyPair,
            app_id: int,
            referrer_address: str,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('get_escrow_by_referrer'),
            sp=params,
            method_args=[
                referrer_address,
            ],
            boxes=[
                (app_id, bytes([0x00]) + encoding.decode_address(referrer_address)),
            ],
            signer=AccountTransactionSigner(user.sk),
        )
        return composer


    def prepare_get_referrer_by_escrow(self,
            user: KeyPair,
            app_id: int,
            escrow_address: str,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('get_referrer_by_escrow'),
            sp=params,
            method_args=[
                escrow_address,
            ],
            boxes=[
                (app_id, bytes([0x01]) + encoding.decode_address(escrow_address)),
            ],
            signer=AccountTransactionSigner(user.sk),
        )
        return composer


    def _get_defaults(self,
              composer: Optional[AtomicTransactionComposer] = None,
              params: Optional[SuggestedParams] = None):
        if composer is None:
            composer = AtomicTransactionComposer()
        if params is None:
            params = self.algod_client.suggested_params()
            params.flat_fee = True
            params.fee = 1000
        return composer, params


    def _read_contract(self):
        filename = os.path.dirname(os.path.realpath(__file__)) + '/../abis/treasury.json'
        with open(filename) as f:
            contract_raw = f.read()
        return Contract.from_json(contract_raw)
