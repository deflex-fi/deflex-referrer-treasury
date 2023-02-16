# Deflex Referrer Treasury App

Clients that integrate Deflex earn a commission for every swap that is
performed on their platform and they can provide a *referrer address* which
receives this commission. Since Deflex charges fees in the output asset the
referrer address must be opted into many different ASAs to actually earn the
commission. If the referrer address isn't opted into an asset, it cannot
receive the commission.

Therefore, we use this app to pool commissions that can later be claimed by the
referrer. For every referrer, an escrow account is created that's rekeyed to
this app. If an asset is swapped that this escrow hasn't received before, the
escrow is automatically opted into it.

The referrer can claim the pooled commissions at any time.



## State

The app keeps all state in box storage. We maintain two maps, one from the
referrer address to its escrow address and vice versa.

### Map: Referrer -> Escrow

Key:   `(0x00, referrer_address)`
Value: `escrow_address`
Length: 1 + 32 + 32 = 65 bytes

Cost per box entry:
- 0.0025 ALGO for box creation
- 0.0004 Algos * 65 = 0.026
- Total: 0.0285


### Map: Escrow -> Referrer

Key:   `(0x01, escrow_address)`
Value: `referrer_address`
Length: 1 + 32 + 32 = 65 bytes

Cost per box entry:
- 0.0025 ALGO for box creation
- 0.0004 Algos * 65 = 0.26
- Total: 0.0285


## Methods

### Registering an escrow account: `Referrer_register_escrow`

Registers an escrow account that collects commissions for a referrer. A
referrer can have at most one escrow account.

Parameters:
1. `referrer_address`: the address of the referrer account

Notes:
- This function must be called from the escrow account
- The escrow account rekeys itself to the app account
- The escrow account must contain at least 0.157 ALGO, 0.057 of which are sent
  to the app account to cover for the MBR increase due to the boxes

Required network fees: `2 * minfee`
- `1 * minfee` microALGO for the call itself
- `1 * minfee` to send 0.057 ALGO to the app account

Box references:
- `(0x00, referrer_address)`
- `(0x01, escrow_address)`


### Claiming commissions: `Referrer_claim`

This claims a referrer's commissions from her escrow account and transfers them
to a beneficiary account.

Parameters:
1. `escrow`: the escrow account that holds the commissions
2. `beneficiary`: the beneficiary account that receives the commissions
3. `beneficiary`: the asset for which the commissions are claimed (0 if ALGO)
4. `amount`: the amount that is claimed (0 to claim all)

Required network fees: `2 * minfee`
- `1 * minfee` microALGO for the call itself
- `1 * minfee` to send the commission to the beneficiary

Notes:
- This function must be called by the referrer


## Transaction Groups
