#pragma version 8

const int ALGO_ID = 0
const bytes ESCROW_TEMPLATE = "\x08\x80\x28\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xff\xff\xff\xff\xff\xff\xff\xff\x35\x00\x80\x05\x61\x70\x70\x49\x44\x34\x00\x81\x20\x5b\x16\x50\x03\x35\x01\x31\x18\x34\x00\x81\x20\x5b\x12\x44\x31\x19\x81\x00\x12\x44\x31\x20\x34\x01\x12\x44\x36\x1a\x00\x80\x04\x5c\x96\xed\x70\x12\x44\x36\x1a\x01\x34\x00\x57\x00\x20\x12\x44\x81\x01\x43"

if Txn.ApplicationID == 0:
    # Create app
    exit(1)
end

switch Txn.OnCompletion:
    NoOp: main
    OptIn: opt_in
    CloseOut: close_out
    UpdateApplication: update_app
    DeleteApplication: delete_app
end

block opt_in:
    # Disallow Opt In
    exit(0)
end

block close_out:
    # Disallow Closing Out
    exit(0)
end

block update_app:
    # Disallow upating the app
    exit(0)
end

block delete_app:
    # Disallow deleting the app
    exit(0)
end

block main:
    switch Txn.ApplicationArgs[0]:
        method("register_escrow(address)void"): register_escrow
        method("claim(account,account)void"): claim
        method("referrer_claim(account,account,asset,uint64,uint64)uint64"): referrer_claim
        method("opt_escrow_into_assets(pay,account)void"): opt_escrow_into_assets
        method("get_escrow_by_referrer(address)address"): get_escrow_by_referrer
    end


    block register_escrow:
        # the escrow must be rekeyed to the app
        assert(Txn.RekeyTo == Global.CurrentApplicationAddress)
        assert(Txn.CloseRemainderTo == Global.ZeroAddress)
        assert(Txn.AssetCloseTo == Global.ZeroAddress)

        # check that the (referrer, escrow) accounts are linked
        bytes escrow_address = Txn.Sender
        bytes referrer_address = Txn.ApplicationArgs[1]
        assert_accounts_linked(referrer_address, escrow_address)

        exit(1)
    end


    block claim:
        int referrer_idx = btoi(Txn.ApplicationArgs[1])
        bytes referrer_address = Txn.Accounts[referrer_idx]

        int escrow_idx = btoi(Txn.ApplicationArgs[2])
        bytes escrow_address = Txn.Accounts[escrow_idx]

        # check that the (referrer, escrow) accounts are linked
        assert_accounts_linked(referrer_address, escrow_address)

        int nr_assets = Txn.NumAssets
        for i in 0:nr_assets:
            int asset_id = Txn.Assets[i]
            int amount = get_balance(escrow_idx, asset_id)
            bytes note = "deflex referral program"
            transfer(asset_id, amount, escrow_address, referrer_address, note)
        end

        exit(1)
    end


    block referrer_claim:
        int escrow_idx = btoi(Txn.ApplicationArgs[1])
        bytes escrow_address = Txn.Accounts[escrow_idx]

        # check that the (referrer, escrow) accounts are linked
        bytes referrer_address = Txn.Sender
        assert_accounts_linked(referrer_address, escrow_address)

        int beneficiary_idx = btoi(Txn.ApplicationArgs[2])
        bytes beneficiary_address = Txn.Accounts[beneficiary_idx]

        int asset_idx = btoi(Txn.ApplicationArgs[3])
        int asset_id = Txn.Assets[asset_idx]

        int amount = btoi(Txn.ApplicationArgs[4])

        # the caller specifies 1 to close the asset to the beneficiary (thus
        # freeing up the MBR), and 0 otherwise
        int close_out = btoi(Txn.ApplicationArgs[5])
        assert((close_out == 0) || (close_out == 1))

        # the escrow account's balance for the given asset
        int balance = get_balance(escrow_idx, asset_id)

        # to claim the whole balance of the provided asset, the referrer passes amount=0
        if amount == 0:
            amount = balance
        end

        bytes note = "deflex referral program"
        if close_out == 0:
            transfer(asset_id, amount, escrow_address, beneficiary_address, note)
        else:
            # we only allow closing out assets, the escrow account cannot be closed
            assert(asset_id != ALGO_ID)
            # we set the amount to the asset's balance as we cannot close out an
            # asset only partially
            amount = balance
            inner_txn:
                TypeEnum: Axfer
                Sender: escrow_address
                AssetReceiver: beneficiary_address
                AssetAmount: balance
                XferAsset: asset_id
                AssetCloseTo: beneficiary_address
                Fee: 0
                Note: note
            end
        end

        abi_return(itob(amount))
        exit(1)
    end


    block opt_escrow_into_assets:
        int escrow_idx = btoi(Txn.ApplicationArgs[1])
        bytes escrow_address = Txn.Accounts[escrow_idx]

        # the number of assets that the user wants to opt into
        int nr_assets = Txn.NumAssets

        # check that the previous txn funds the MBR increase
        int input_txn_index = Txn.GroupIndex - 1
        assert(Gtxn[input_txn_index].TypeEnum == Pay)
        assert(Gtxn[input_txn_index].Receiver == escrow_address)
        assert(Gtxn[input_txn_index].Amount == (100_000 * nr_assets))
        assert(Gtxn[input_txn_index].RekeyTo == Global.ZeroAddress)
        assert(Gtxn[input_txn_index].CloseRemainderTo == Global.ZeroAddress)
        assert(Gtxn[input_txn_index].AssetCloseTo == Global.ZeroAddress)

        int skipped_assets = 0
        for i in 0:nr_assets:
            int is_opted_in
            is_opted_in, _ = asset_holding_get(AssetBalance, escrow_idx, Txn.Assets[i])
            if !is_opted_in && (Txn.Assets[i] != ALGO_ID):
                transfer(Txn.Assets[i], 0, escrow_address, escrow_address, "")
            else:
                skipped_assets = skipped_assets + 1
            end
        end

        # send back the MBR increase for assets that were not opted in
        if skipped_assets > 0:
            int amount = 100_000 * skipped_assets
            transfer(ALGO_ID, amount, escrow_address, Txn.Sender, "")
        end

        exit(1)
    end


    block get_escrow_by_referrer:
        bytes referrer_address = Txn.ApplicationArgs[1]
        abi_return(get_escrow_address(referrer_address))
        exit(1)
    end
end


func assert_accounts_linked(referrer_address: bytes, escrow_address: bytes):
    bytes derived_escrow_address = get_escrow_address(referrer_address)
    assert(escrow_address == derived_escrow_address)
    return
end


func get_escrow_address(referrer_address: bytes) bytes:
    assert(len(referrer_address) == 32)
    bytes program = ESCROW_TEMPLATE
    program = replace2( 3, program, referrer_address)
    program = replace2(35, program, itob(Global.CurrentApplicationID))
    return sha512_256(concat("Program", program))
end


func transfer(asset_id: int, amount: int, sender: bytes, receiver: bytes, note: bytes):
    if asset_id == ALGO_ID:
        inner_txn:
            TypeEnum: Pay
            Sender: sender
            Receiver: receiver
            Amount: amount
            Fee: 0
            Note: note
        end
    else:
        inner_txn:
            TypeEnum: Axfer
            Sender: sender
            AssetReceiver: receiver
            AssetAmount: amount
            XferAsset: asset_id
            Fee: 0
            Note: note
        end
    end
    return
end


func get_balance(account_idx: int, asset_id: int) int:
    int balance
    if asset_id == ALGO_ID:
        balance = balance(account_idx) - min_balance(account_idx)
    else:
        int is_opted_in
        is_opted_in, balance = asset_holding_get(AssetBalance, account_idx, asset_id)
        assert(is_opted_in)
    end
    return balance
end


func abi_return(result: bytes):
    log(concat("\x15\x1f\x7c\x75", result))
    return
end
