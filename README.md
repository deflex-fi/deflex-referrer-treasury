# Deflex Referrer Treasury App

Clients that integrate Deflex earn a commission for every swap that is
performed on their platform and they can provide a *referrer address* which
receives this commission. Since Deflex charges fees in the output asset, the
referrer address must be opted into many different ASAs to actually earn the
commission. If the referrer address isn't opted into an asset, it cannot
receive the commission.

Therefore, we use this app to hold commissions in escrow that can later be
claimed by the referrer. For every referrer, an individual escrow account is
created that's rekeyed to this app. If an asset is swapped that this escrow
hasn't received before, the escrow is automatically opted into it.

The commissions can be claimed and sent to the referrer at any time as long as
the referrer has opted into the necessary assets.


## Auto-convert commissions

Accumulating commissions in different assets may be undesirable for some
clients (a token that's valuable today may be worthless by the time the client
claims the commissions). Therefore, we offer a system where we convert
commissions to a pre-defined asset (e.g., ALGO, USDC, etc). This is,
unfortunately, not possible at the moment in a trustless way. Therefore, this
system is by default disabled and only if a client approves with a special
transaction, a dedicated account is given access to a client's escrow. Clients
can grant and revoke permission at any time.

This privileged swapper account, if granted access, can withdraw assets from an
escrow account and swap them to a desired output asset. The swapping involves
off-chain components (computing the swap plan that is then executed with
Deflex) and is therefore not trustless. Again, this system is only enabled for
an escrow, if a client explicitly approves it.


## State

### Global State

- `swapper_address` (bytes): the address of the privileged account that is
  allowed to swap assets on an escrow's behalf.

### Local State of Escrow Accounts

- `swapping_allowed` (uint64): 1 if the referrer grants the swapper access to
  the escrow, 0 otherwise (0 is the default).
- `target_asset_id` (uint64): The ID of the asset that other assets are swapped
  to if swapping is enabled

### Local State MBR

Escrow accounts opt into the app and need to contain at least 0.257 ALGO for
MBR, which is computed as follows:
- 0.1 ALGO for an account MBR
- 0.1 ALGO for opting into the app
- 0.025 + 0.0035 = 0.0285 ALGO for the `swapping_allowed` local state
- 0.025 + 0.0035 = 0.0285 ALGO for the `target_asset_id` local state


## Deterministic Escrow Address

We use a logicsig that is templated with the referrer address and this app's ID
to derive a deterministic address for the escrow account. This logicsig only
permits calling the app's `register_escrow` function.


## Methods

### Registering an escrow account with OptIn

Registers an escrow account that collects commissions for a referrer. A
referrer can have only one escrow account. This function must be called with
`OnComplete=OptIn`.

Parameters:
1. `referrer_address`: the address of the referrer account that is escrow is
   linked to.

Required network fees: `1 * minfee`
- `1 * minfee` microALGO for the call itself

Notes:
- This function must be called from the escrow account
- The escrow account must rekey itself to the app account
- Once an escrow is rekeyed to a referrer, it cannot be unlinked anymore.
- The escrow must contain at least 0.257 ALGO to cover for its MBR.


### Claiming commissions in bulk: `claim_bulk`

This claims a referrer's commissions from her escrow account and transfers them
to the referrer account.

The assets for which the commissions are claimed need to be specified in the
transaction's foreign assets array. To claim ALGO, specify `0` in the foreign
assets array.

Parameters:
1. `referrer`: the referrer's account that receives the commissions
2. `escrow`: the referrer's escrow account that holds the commissions

Required network fees: `minfee * (1 + len(foreign_assets))`
- `1 * minfee` microALGO for the call itself
- `len(foreign_assets) * minfee` to send the commission to the referrer

Notes:
- This function can be invoked by anyone, but only allows to send funds from a
  escrow to its linked referrer.
- We thought about allowing only the referrer to claim its fees, but if the
  referrer is, e.g., a smart-contract governed by a DAO it may not be able to
  issue the necessary transactions.


### Claiming commissions as referrer: `claim_single`

This claims a referrer's commissions from her escrow account and transfers them
to the referrer account. There are two important differences with respect to
the previous function:

1. This function can only be called by the referrer account, or if the referrer
   allowed it, by the privileged swapper account.
2. This function allows closing out an asset (ALGO cannot be closed out).

Parameters:
1. `escrow`: the referrer's escrow account that holds the commissions
2. `beneficiary`: the beneficiary account that receives the asset
3. `asset`: the asset that is claimed (0 if ALGO)
4. `amount`: the amount of the asset that is claimed (0 to claim it all)
5. `close_out`: 1 if the asset is to be closed out, 0 otherwise

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


### Enable swapping: `enable_swapping`

Grants the permission to let the privileged swapper account withdraw from a
referrer's escrow account. If granted, the swapper can withdraw any asset but
the `target_asset` that the referrer specifies in this call. The idea is that
the swapper swaps assets to the `target_asset` and sends them back to the
escrow account (and for that the swapper doesn't need to be able to withdraw
the `target_asset` from the escrow). This function can only be called by the
referrer account that owns this escrow account.

Parameters:
1. `escrow`: the referrer's escrow account
2. `target_asset`: the ID of the asset (0 for ALGO) that other assets are swapped to

Required network fees: `1 * minfee`

Notes:
- The escrow account must be opted into the `target_asset`


### Disable swapping: `disable_swapping`

Lets a referrer revoke the permission to let the privileged swapper account
withdraw from their escrow account

Parameters:
1. `escrow`: the referrer's escrow account

Required network fees: `1 * minfee`


### Setting the privileged swapper account: `set_swapper_address`

Lets the app's creator define a privileged swapper account that is allowed to
withdraw from accounts for which it was given access to. This function can only
be called by this app's creator account.

Parameters:
1. `swapper`: the address of the swapper

Required network fees: `1 * minfee`


### Getting a referrer's escrow address: `get_escrow_by_referrer`

Return a referrer's registered escrow address.

Parameters:
1. `referrer`: the referrer's address

Required network fees: `1 * minfee`


## Transaction Groups

### Registering an escrow

1. Payment _(to increase the minimum balance of the limit-order app)_
   1. Sender: Any Account
   2. Receiver: Escrow account
   3. Amount: `228_500` (MBR for account)
2. Application _(to initialize the app)_
   1. ID: Referrer Treasury App
   2. Sender: Escrow account
   3. Args: [Referrer address]
   4. On Complete: OptIn
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
