#pragma version 8

struct MapValue:
  address: bytes[32]
end

const int ALGO_ID = 0
const bytes MAP_ID_REFERRER_ESCROW = "\x00"
const bytes MAP_ID_ESCROW_REFERRER = "\x01"


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
        method("get_referrer_by_escrow(address)address"): get_referrer_by_escrow
    end


    block register_escrow:
        assert(Txn.CloseRemainderTo == Global.ZeroAddress)
        assert(Txn.AssetCloseTo == Global.ZeroAddress)
        assert(Txn.RekeyTo == Global.CurrentApplicationAddress)

        bytes escrow_address = Txn.Sender
        bytes referrer_address = Txn.ApplicationArgs[1]
        assert(len(referrer_address) == 32)
        assert(referrer_address != escrow_address)
        assert(referrer_address != Global.ZeroAddress)
        assert(escrow_address != Global.ZeroAddress)

        # cover the MBR increase in the app account due to the boxes by
        # taking the necessary 0.057 ALGO from the escrow account
        transfer(ALGO_ID, 57000, escrow_address, Global.CurrentApplicationAddress, "")

        # asserts that the box does not exist yet
        bytes key_referrer_to_escrow = concat(MAP_ID_REFERRER_ESCROW, referrer_address)
        box<MapValue> box_referrer_to_escrow = CreateBox(key_referrer_to_escrow)
        box_referrer_to_escrow.address = escrow_address

        # asserts that the box does not exist yet
        bytes key_escrow_to_referrer = concat(MAP_ID_ESCROW_REFERRER, escrow_address)
        box<MapValue> box_escrow_to_referrer = CreateBox(key_escrow_to_referrer)
        box_escrow_to_referrer.address = referrer_address

        exit(1)
    end


    block claim:
        int referrer_idx = btoi(Txn.ApplicationArgs[1])
        bytes referrer_address = Txn.Accounts[referrer_idx]

        int escrow_idx = btoi(Txn.ApplicationArgs[2])
        bytes escrow_address = Txn.Accounts[escrow_idx]

        # check that the (referrer, escrow) accounts are linked
        bytes key_referrer_to_escrow = concat(MAP_ID_REFERRER_ESCROW, referrer_address)
        box<MapValue> box_referrer_to_escrow = OpenBox(key_referrer_to_escrow)
        assert(box_referrer_to_escrow.address == escrow_address)

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
        bytes referrer_address = Txn.Sender

        int escrow_idx = btoi(Txn.ApplicationArgs[1])
        bytes escrow_address = Txn.Accounts[escrow_idx]

        int beneficiary_idx = btoi(Txn.ApplicationArgs[2])
        bytes beneficiary_address = Txn.Accounts[beneficiary_idx]

        int asset_idx = btoi(Txn.ApplicationArgs[3])
        int asset_id = Txn.Assets[asset_idx]

        int amount = btoi(Txn.ApplicationArgs[4])

        # the caller specifies 1 to close the asset to the beneficiary (thus
        # freeing up the MBR), and 0 otherwise
        int close_out = btoi(Txn.ApplicationArgs[5])
        assert((close_out == 0) || (close_out == 1))

        # check that the (referrer, escrow) accounts are linked
        bytes key_referrer_to_escrow = concat(MAP_ID_REFERRER_ESCROW, referrer_address)
        box<MapValue> box_referrer_to_escrow = OpenBox(key_referrer_to_escrow)
        assert(box_referrer_to_escrow.address == escrow_address)

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
        bytes key_referrer_to_escrow = concat(MAP_ID_REFERRER_ESCROW, referrer_address)

        bytes escrow_address = Global.ZeroAddress
        int length
        int found
        length, found = box_len(key_referrer_to_escrow)
        if found:
            box<MapValue> box_referrer_to_escrow = OpenBox(key_referrer_to_escrow)
            escrow_address = box_referrer_to_escrow.address
        end

        abi_return(escrow_address)
        exit(1)
    end


    block get_referrer_by_escrow:
        bytes escrow_address = Txn.ApplicationArgs[1]
        bytes key_escrow_to_referrer = concat(MAP_ID_ESCROW_REFERRER, escrow_address)

        bytes referrer_address = Global.ZeroAddress
        int length
        int found
        length, found = box_len(key_escrow_to_referrer)
        if found:
            box<MapValue> box_escrow_to_referrer = OpenBox(key_escrow_to_referrer)
            referrer_address = box_escrow_to_referrer.address
        end

        abi_return(referrer_address)
        exit(1)
    end
end


func transfer(asset_id: int, amount: int, sender: bytes, receiver: bytes, note: bytes):
    if asset_id == 0:
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
