#pragma version 8

struct Configuration:
  referrer_address: bytes[32]
  application_id: int
end

Configuration config = "\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xDD\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"

# compute the address of the provided app
bytes app_address = sha512_256(concat("appID", itob(config.application_id)))

# Only allow calling the register_escrow method on the correct app
# with the correct referrer_address
assert(Txn.ApplicationID == config.application_id)
assert(Txn.OnCompletion == NoOp)
assert(Txn.RekeyTo == app_address)
assert(Txn.ApplicationArgs[0] == method("register_escrow(address)void"))
assert(Txn.ApplicationArgs[1] == config.referrer_address)
exit(1)
