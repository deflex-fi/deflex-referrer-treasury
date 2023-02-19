#pragma version 8

const int ALGO_ID = 0
const bytes ESCROW_TEMPLATE = "\x08\x80\x28\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xdd\xff\xff\xff\xff\xff\xff\xff\xff\x35\x00\x80\x05\x61\x70\x70\x49\x44\x34\x00\x81\x20\x5b\x16\x50\x03\x35\x01\x31\x18\x34\x00\x81\x20\x5b\x12\x44\x31\x19\x81\x01\x12\x44\x31\x20\x34\x01\x12\x44\x36\x1a\x00\x34\x00\x57\x00\x20\x12\x44\x81\x01\x43"

# global and local state keys
# - global state keys are prefixed by VG (variable in global state)
# - local state keys are prefixed by VL (variable in local state)
const bytes VG_SWAPPER_ADDRESS = "swapper_address"
const bytes VL_SWAPPING_ALLOWED = "swapping_allowed"

const int SWAPPING_DISALLOWED = 0
const int SWAPPING_ALLOWED = 1

if Txn.ApplicationID == 0:
    app_global_put(VG_SWAPPER_ADDRESS, Global.ZeroAddress)
    exit(1)
end

switch Txn.OnCompletion:
    NoOp: main
    OptIn: opt_in
    CloseOut: close_out
    UpdateApplication: update_app
    DeleteApplication: delete_app
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

block opt_in:
    # the escrow must be rekeyed to the app
    assert(Txn.RekeyTo == Global.CurrentApplicationAddress)
    assert(Txn.CloseRemainderTo == Global.ZeroAddress)
    assert(Txn.AssetCloseTo == Global.ZeroAddress)

    # check that the (referrer, escrow) accounts are linked
    bytes escrow_address = Txn.Sender
    bytes referrer_address = Txn.ApplicationArgs[0]
    assert(is_authoritative_account(referrer_address, escrow_address))

    # disallow swapping for this escrow account by default
    app_local_put(escrow_address, VL_SWAPPING_ALLOWED, SWAPPING_DISALLOWED)

    exit(1)
end

block main:
    switch Txn.ApplicationArgs[0]:
        method("claim_bulk(account,account)void"): claim_bulk
        method("claim_single(account,account,asset,uint64,uint64)uint64"): claim_single
        method("opt_escrow_into_assets(pay,account)void"): opt_escrow_into_assets
        method("set_escrow_permissions(account,uint64)void"): set_escrow_permissions
        method("set_swapper_address(address)void"): set_swapper_address
        method("get_escrow_by_referrer(address)address"): get_escrow_by_referrer
    end


    block claim_bulk:
        int referrer_idx = btoi(Txn.ApplicationArgs[1])
        bytes referrer_address = Txn.Accounts[referrer_idx]

        int escrow_idx = btoi(Txn.ApplicationArgs[2])
        bytes escrow_address = Txn.Accounts[escrow_idx]

        # check that the (referrer, escrow) accounts are linked
        assert(is_authoritative_account(referrer_address, escrow_address))

        int nr_assets = Txn.NumAssets
        for i in 0:nr_assets:
            int asset_id = Txn.Assets[i]
            int amount = get_balance(escrow_idx, asset_id)
            bytes note = "deflex:udeflex_commission"
            transfer(asset_id, amount, escrow_address, referrer_address, note)
        end

        exit(1)
    end


    block claim_single:
        int escrow_idx = btoi(Txn.ApplicationArgs[1])
        bytes escrow_address = Txn.Accounts[escrow_idx]

        # this function can be called by one or two entities:
        # 1. the referrer is always allowed to call this function.
        # 2. if the referrer granted access to the swapper_address, the
        #    swapper_address is allowed to withdraw from the escrow
        if !is_authoritative_account(Txn.Sender, escrow_address):
            bytes swapper_address = app_global_get(VG_SWAPPER_ADDRESS)
            assert(swapper_address != Global.ZeroAddress)
            int swapping_allowed = app_local_get(escrow_address, VL_SWAPPING_ALLOWED)
            assert(swapping_allowed && (Txn.Sender == swapper_address))
        end

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

        bytes note = "deflex:udeflex_commission"
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


    block set_escrow_permissions:
        int escrow_idx = btoi(Txn.ApplicationArgs[1])
        bytes escrow_address = Txn.Accounts[escrow_idx]

        # only the referrer is allowed to set their escrow's permissions
        bytes referrer_address = Txn.Sender
        assert(is_authoritative_account(referrer_address, escrow_address))

        int permission = btoi(Txn.ApplicationArgs[2])
        assert((permission == SWAPPING_ALLOWED) || (permission == SWAPPING_DISALLOWED))
        app_local_put(escrow_address, VL_SWAPPING_ALLOWED, permission)

        exit(1)
    end


    block set_swapper_address:
        # only the creator is allowed to call this function
        assert(Txn.Sender == Global.CreatorAddress)

        bytes swapper_address = Txn.Accounts[1]
        assert(len(swapper_address) == 32)
        app_global_put(VG_SWAPPER_ADDRESS, swapper_address)

        exit(1)
    end


    block get_escrow_by_referrer:
        bytes referrer_address = Txn.ApplicationArgs[1]
        abi_return(get_escrow_address(referrer_address))
        exit(1)
    end
end


func is_authoritative_account(referrer_address: bytes, escrow_address: bytes) int:
    bytes derived_escrow_address = get_escrow_address(referrer_address)
    return escrow_address == derived_escrow_address
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
