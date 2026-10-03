# deploy/vmsworker-policy.hcl — bound to job vmsworker's workload identity.
# A worker writes its epochs (by CAS, when it starts a camera), its slot
# (by CAS, when it claims a name) and what a device it holds can say and do,
# and nothing else. verify-bench.sh proves
# the "nothing else" from inside an allocation.
namespace "default" {
  variables {
    path "secrets/vms"          { capabilities = ["read"] }   # the cluster's key: this job and two others (console, vmsworker, recworker), nobody else
    path "vms/epoch/*"  { capabilities = ["write", "read", "list"] }
    path "vms/slots/*"  { capabilities = ["write", "read", "list"] }
    path "vms/holds/*"  { capabilities = ["write", "read", "list"] }    # the place it took — a claim about this process, like its slot
    path "vms/devices/*" { capabilities = ["write", "read", "list"] }   # what a device it holds turned out to be (М10B Lesson 25)
    path "objects/vms/heartbeats/*" { capabilities = ["write", "read", "list"] }   # its heartbeat, as an object-as-Variable
    # The mark a holder leaves BEFORE it calls a device (М10B Lesson 4): "I am about to perform request r1".
    # Whoever holds the device next reads it and does not pulse the door a second time. `destroy`: the mark
    # of a request that no longer exists is cleared by whichever worker gets there.
    path "objects/vms/commands/*"   { capabilities = ["write", "read", "list", "destroy"] }
    path "objects/vms/*" { capabilities = ["read", "list"] }            # the snapshot and the blobs: read, never written by a worker
    path "vms/*"        { capabilities = ["read", "list"] }
    path "platform/schema"      { capabilities = ["read"] }   # the store's schema, checked first (`check_schema`; М10's eighth review)
    path "platform/decommission/*" { capabilities = ["read"] }   # a process on a decommissioned server is given no slot (`Worker._claim_slot`; М10A Lesson 7, step 7)
    # WHAT THE GATE READS (М10's eighth review: no policy let anybody read `domain/*`, and the stand enforces no read
    # ACL — on a real Nomad the gate was a 403 and failed shut). On every request at the playback door
    # (`playback_refusal`) the key set, and while there is none the row that says this cluster is a member all the
    # same (`w2cplatform/access.py`, `TRUST_KEYS`, `MEMBER_MARK`). Read only: the domain's agent writes them. Nothing
    # else of `domain/*` (М10's ninth review): the door verifies no token, so the grants and the emergency password's
    # hash are none of its business.
    path "domain/keys"          { capabilities = ["read"] }
    path "domain/member"        { capabilities = ["read"] }
  }
}
