import tealish
import os
import base64
from typing import List, Optional

from algosdk.atomic_transaction_composer import AtomicTransactionComposer, AccountTransactionSigner, TransactionWithSigner, LogicSigTransactionSigner
from algosdk.transaction import SuggestedParams, LogicSigAccount
from algosdk import transaction
from algosdk.transaction import StateSchema
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
        with open(basepath + "escrow_template.tl") as f:
            self.template_tealish = f.read()
            self.template_teal, _  = tealish.compile_program(self.template_tealish)
            self.template_teal = '\n'.join(self.template_teal)
            self.template_bytecode = self.compile_program(self.template_teal)
        self.contract = self._read_contract()


    def compile_program(self, source_code):
        compile_response = self.algod_client.compile(source_code)
        return base64.b64decode(compile_response['result'])


    def escrow_logicsig(self, referrer_address: str, app_id: int):
        raw_address = encoding.decode_address(referrer_address)
        raw_app_id = app_id.to_bytes(8, byteorder='big')
        template = self._overwrite(self.template_bytecode, raw_address + raw_app_id, 3)
        return transaction.LogicSigAccount(template)


    def escrow_address(self, referrer_address: str, app_id: int):
        return self.escrow_logicsig(referrer_address, app_id).address()


    def escrow_template(self):
        """Prints the escrow template in a format that can be put into tealish code"""
        return "".join(['\\x%02x' % b for b in self.template_bytecode])


    def get_global_schema(self):
        global_ints  = 0
        global_bytes = 1
        return StateSchema(global_ints, global_bytes)


    def get_local_schema(self):
        local_ints  = 2
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


    def prepare_register_escrow(self,
            user: KeyPair,
            app_id: int,
            referrer_address: str,
            escrow: LogicSigAccount = None,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        if escrow == None:
            escrow = self.escrow_logicsig(referrer_address, app_id)
        # fund escrow
        composer = composer.add_transaction(TransactionWithSigner(transaction.PaymentTxn(
            sender=user.pk,
            sp=params,
            receiver=escrow.address(),
            amt=257_000,
        ), AccountTransactionSigner(user.sk)))
        composer.txn_list[-1].txn.fee = 2000
        # call app
        composer = composer.add_transaction(TransactionWithSigner(transaction.ApplicationCallTxn(
            sender=escrow.address(),
            sp=params,
            index=app_id,
            app_args=[
                encoding.decode_address(referrer_address),
            ],
            rekey_to=self.app_address(app_id),
            on_complete=transaction.OnComplete.OptInOC.real,
        ), LogicSigTransactionSigner(escrow)))
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
            method=self.contract.get_method_by_name('opt_escrow_into_assets'),
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


    def prepare_claim_bulk(self,
            user: KeyPair,
            app_id: int,
            referrer_address: str,
            escrow_address: str,
            asset_ids: List[int],
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('claim_bulk'),
            sp=params,
            method_args=[
                referrer_address,
                escrow_address,
            ],
            foreign_assets=asset_ids,
            signer=AccountTransactionSigner(user.sk),
        )
        composer.txn_list[-1].txn.fee = 1000 * (1 + len(asset_ids))
        return composer


    def prepare_claim_single(self,
            user: KeyPair,
            app_id: int,
            escrow_address: str,
            asset_id: int,
            amount: int,
            close_out: bool = False,
            beneficiary_address: str = None,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        if beneficiary_address == None:
            beneficiary_address = user.pk
        composer, params = self._get_defaults(composer, params)
        composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('claim_single'),
            sp=params,
            method_args=[
                escrow_address,
                beneficiary_address,
                asset_id,
                amount,
                1 if close_out else 0,
            ],
            signer=AccountTransactionSigner(user.sk),
        )
        composer.txn_list[-1].txn.fee = 2000
        return composer


    def prepare_enable_swapping(self,
            user: KeyPair,
            app_id: int,
            escrow_address: str,
            target_asset_id: int,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('enable_swapping'),
            sp=params,
            method_args=[
                escrow_address,
                target_asset_id,
            ],
            signer=AccountTransactionSigner(user.sk),
        )
        return composer


    def prepare_disable_swapping(self,
            user: KeyPair,
            app_id: int,
            escrow_address: str,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('disable_swapping'),
            sp=params,
            method_args=[
                escrow_address,
            ],
            signer=AccountTransactionSigner(user.sk),
        )
        return composer


    def prepare_set_swapper_address(self,
            user: KeyPair,
            app_id: int,
            swapper_address: str,
            composer: Optional[AtomicTransactionComposer] = None,
            params: Optional[SuggestedParams] = None) -> AtomicTransactionComposer:
        composer, params = self._get_defaults(composer, params)
        composer.add_method_call(
            app_id=app_id,
            sender=user.pk,
            method=self.contract.get_method_by_name('set_swapper_address'),
            sp=params,
            method_args=[
                swapper_address,
            ],
            signer=AccountTransactionSigner(user.sk),
        )
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


    def _overwrite(self, target: list, new_content: list, start_pos: int) -> list:
        return target[:start_pos] + new_content + target[start_pos+len(new_content):]
