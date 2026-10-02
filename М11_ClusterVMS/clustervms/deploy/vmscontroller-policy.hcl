# deploy/vmscontroller-policy.hcl — bound to job vmscontroller's workload identity.
# The only writer of PLACEMENT: which worker runs which camera, a released
# slot's redistribution, an operator's `retire`, and the snapshot that leaves
# the cluster. It never writes a camera row — those are the console's.
namespace "default" {
  variables {
    path "vms/workers/*"        { capabilities = ["write", "read", "list"] }
    path "vms/placement/*"      { capabilities = ["write", "read", "list"] }
    path "vms/slots/*"          { capabilities = ["write", "read", "list"] }
    path "objects/vms/snapshot/*" { capabilities = ["write", "read", "list"] }   # one object per worker (М10A Lesson 25)
    path "objects/*"            { capabilities = ["read", "list"] }
    # WHAT IT READS, NOT EVERYTHING (М10's eighth review): it had `path "*"`, which read `secrets/vms` too — the key
    # the console's policy says only three jobs read. The rows it places from, the other subsystem's rows its
    # placement asks about, the heartbeats and snapshots, the platform's rows (`drain`, `schema`); never `secrets/*`,
    # never `domain/*`. `tests/test_policies.py` checks every read the code makes against this list.
    path "vms/*"                { capabilities = ["read", "list"] }
    path "rec/*"                { capabilities = ["read", "list"] }   # a recording's epoch: where a camera's backup records
    path "platform/*"           { capabilities = ["read", "list"] }
  }
}
