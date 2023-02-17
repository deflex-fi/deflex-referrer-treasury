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

The pooled commissions can be claimed and sent to the referrer any time as long
as the referrer has opted into the necessary assets.


## State

The app keeps all state in box storage. We maintain two maps, one from the
referrer address to its escrow address and vice versa.

### Map: Referrer -> Escrow

Schema:
- Key:   `(0x00, referrer_address)`
- Value: `escrow_address`
- Length: 1 + 32 + 32 = 65 bytes

Cost per box entry:
- 0.0025 ALGO for box creation
- 0.0004 Algos * 65 = 0.026
- Total: 0.0285


### Map: Escrow -> Referrer

Schema:
- Key:   `(0x01, escrow_address)`
- Value: `referrer_address`
- Length: 1 + 32 + 32 = 65 bytes

Cost per box entry:
- 0.0025 ALGO for box creation
- 0.0004 Algos * 65 = 0.26
- Total: 0.0285


## Methods

### Registering an escrow account: `register_escrow`

Registers an escrow account that collects commissions for a referrer. A
referrer can have at most one escrow account.

Parameters:
1. `referrer_address`: the address of the referrer account that is escrow is
   linked to.

Box references:
- `(0x00, referrer_address)`
- `(0x01, escrow_address)`

Required network fees: `2 * minfee`
- `1 * minfee` microALGO for the call itself
- `1 * minfee` to send 0.057 ALGO to the app account

Notes:
- This function must be called from the escrow account
- The escrow account must rekey itself to the app account
- The escrow account must contain at least 0.157 ALGO, 0.057 of which are sent
  to the app account to cover for the MBR increase due to the boxes
- Once an escrow is linked to a referrer, it cannot be unlinked anymore. This
  allows for easier caching of (referrer, escrow) mappings on the application
  side (otherwise we'd need too many indexer lookups).


### Claiming commissions: `claim`

This claims a referrer's commissions from her escrow account and transfers them
to the referrer account.

The assets for which the commissions are claimed need to be specified in the
transaction's foreign assets array. To claim ALGO, specify `0` in the foreign
assets array.

Parameters:
1. `referrer`: the referrer's account that receives the commissions
2. `escrow`: the referrer's escrow account that holds the commissions

Box references:
- `(0x00, referrer_address)`

Required network fees: `minfee * (1 + len(foreign_assets))`
- `1 * minfee` microALGO for the call itself
- `len(foreign_assets) * minfee` to send the commission to the referrer

Notes:
- This function can be invoked by anyone, but only allows to send funds from a
  escrow to its linked referrer.
- We thought about allowing only the referrer to claim its fees, but if the
  referrer is, e.g., a smart-contract governed by a DAO it may not be able to
  issue the necessary transactions.


### Claiming commissions as referrer: `referrer_claim`

This claims a referrer's commissions from her escrow account and transfers them
to the referrer account. The difference with respect to the previous function
is that this function can only be called by the referrer account itself and
that it allows closing out an asset (ALGO cannot be closed out).

Parameters:
1. `escrow`: the referrer's escrow account that holds the commissions
2. `beneficiary`: the beneficiary account that receives the asset
3. `asset`: the asset that is claimed (0 if ALGO)
4. `amount`: the amount of the asset that is claimed (0 to claim it all)
5. `close_out`: 1 if the asset is to be closed out, 0 otherwise

Box references:
- `(0x00, referrer_address)`

Required network fees: `2* minfee`
- `1 * minfee` microALGO for the call itself
- `1 * minfee` to send the commission to the referrer

Notes:
- Trying to close out ALGO fails
- One can only close out the escrow account's full balance of an asset


### Opting an escrow into assets: `opt_escrow_into_assets`

This opts an escrow account into the assets that are specified in the
transaction's foreign assets array

The transaction must be preceded by a payment transaction that covers the
minimum balance increase for the assets that are opted in (100'000 microALGO
per asset). For instance, if the user wants to opt into five assets, there must
be a payment transaction that sends 500'000 microALGO to the app account.

If the user provides assets that the app has already opted into previously,
then the user is immediately sent back the locked ALGO for that. For instance,
assume the escrow is opted into assets A1 and A2. Now the user calls
`opt_escrow_into_assets(e, [A2,A3,A4,A1])` and provides a payment of 400'000
microALGO. Then the app sends back 200'000 microALGO since assets A1 and A2 are
already opted in.

Parameters:
1. `escrow`: the escrow account that is to be opted into the assets

Required network fees: `minfee * (1 + len(foreign_assets))`
- `1 * minfee` microALGO for the call itself
- `len(foreign_assets) * minfee` to send the commission to the referrer


### Getting a referrer's escrow address: `get_escrow_by_referrer`

Return a referrer's registered escrow address (and the zero-address if none
exists).

Parameters:
1. `referrer`: the referrer's address

Box references:
- `(0x00, referrer_address)`

Required network fees: `1 * minfee`


### Getting an escrow's linked referrer address: `get_referrer_by_escrow`

Return the referrer address that's linked to the provided escrow (and the
zero-address if none exists).

Parameters:
1. `escrow`: the escrow's address

Box references:
- `(0x01, escrow_address)`

Required network fees: `1 * minfee`



## Transaction Groups

### Registering an escrow

1. Payment _(to increase the minimum balance of the limit-order app)_
   1. Sender: Any Account
   2. Receiver: Escrow account
   3. Amount: `157_000` (MBR for account and box storage)
2. Application _(to initialize the app)_
   1. ID: Referrer Treasury App
   2. Method: `register_escrow`
   3. Sender: Escrow account
   4. Args: [Referrer address]
   5. On Complete: NoOp
   6. Rekey to: Referrer Treasury App



## Compiling & building contracts

Initialize a venv environment with `python -m venv env`, activate it with
`source env/bin/activate` and install all the dependencies with:

```sh
pip install -r requirements.txt
```

To compile the contracts from tealish to teal, run:

```sh
tealish compile contracts/
```

To compile the contracts from tealish to teal and binary, run:

```sh
tealish build contracts/
```

The compiled and built contracts are then located in `./contracts/build/`


## Testing

First, get an Algorand sandbox up and running.

To execute all tests, run:

```sh
python -m unittest discover tests/
```

To execute a single test file, run for example:

```sh
python tests/test_claim.py
```
