# The signer is the only writer of its keys, its users, and what it publishes to agents.
namespace "default" {
  variables {
    path "domain/signer"    { capabilities = ["read", "write"] }
    path "identity/*"       { capabilities = ["read", "write"] }
    path "domain/keys"      { capabilities = ["read", "write"] }
    path "domain/revoked"   { capabilities = ["read", "write"] }
    path "domain/licence"   { capabilities = ["read", "write"] }
    path "domain/placement" { capabilities = ["read", "write"] }
    path "domain/placement/*" { capabilities = ["read", "write"] }
    # The books (domain/books.py), one per member, and what they are built from.
    path "domain/sources/*"   { capabilities = ["read", "write"] }
    path "domain/primaries/*" { capabilities = ["read", "write"] }
    path "domain/poll/*"      { capabilities = ["read", "write"] }
    path "domain/upstream/*"  { capabilities = ["read", "write"] }
    path "domain/asks/*"      { capabilities = ["read", "write", "list"] }   # list: a book no scenario fills any more is emptied
    path "domain/crossings"   { capabilities = ["read"] }
    path "domain/shared"      { capabilities = ["read"] }
    path "domain/topology"    { capabilities = ["read"] }      # the operator's topology: the centre, the star
    path "domain/members"     { capabilities = ["read", "write"] }
    path "domain/roads"       { capabilities = ["read", "write"] }   # cameras sent to push after a recorder could not pull   # the registrar admits, a leave removes; the books pass reads
  }
}
