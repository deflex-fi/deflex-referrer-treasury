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
        inner_txn:
            TypeEnum: Pay
            Sender: escrow_address
            Receiver: Global.CurrentApplicationAddress
            Amount: 57000
            Fee: 0
        end

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
            int balance
            if asset_id == ALGO_ID:
                balance = balance(escrow_idx) - min_balance(escrow_idx)
                inner_txn:
                    TypeEnum: Pay
                    Sender: escrow_address
                    Receiver: referrer_address
                    Amount: balance
                    Fee: 0
                    Note: "deflex referral program"
                end
            else:
                int found
                found, balance = asset_holding_get(AssetBalance, escrow_idx, asset_id)
                assert(found)
                inner_txn:
                    TypeEnum: Axfer
                    Sender: escrow_address
                    AssetReceiver: referrer_address
                    AssetAmount: balance
                    XferAsset: asset_id
                    Fee: 0
                    Note: "deflex referral program"
                end
            end
        end

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
                inner_txn:
                    TypeEnum: Axfer
                    Sender: escrow_address
                    AssetReceiver: escrow_address
                    XferAsset: Txn.Assets[i]
                    Amount: 0
                    Fee: 0
                end
            else:
                skipped_assets = skipped_assets + 1
            end
        end

        # send back the MBR increase for assets that were not opted in
        if skipped_assets > 0:
            inner_txn:
                TypeEnum: Pay
                Sender: escrow_address
                Receiver: Txn.Sender
                Amount: 100_000 * skipped_assets
                Fee: 0
            end
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


func abi_return(result: bytes):
    log(concat("\x15\x1f\x7c\x75", result))
    return
end
