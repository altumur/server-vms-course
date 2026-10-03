# deploy/reccontroller-policy.hcl — bound to job reccontroller's workload identity.
# The only writer of the recorder's PLACEMENT — which recorder writes which
# camera's footage. Never a recording row (the console's), never the VMS's.
namespace "default" {
  variables {
    path "rec/workers/*"   { capabilities = ["write", "read", "list"] }
    path "rec/placement/*" { capabilities = ["write", "read", "list"] }
    path "rec/slots/*"     { capabilities = ["write", "read", "list"] }
    path "rec/decommissioned/*" { capabilities = ["write", "read", "list", "destroy"] }   # its mark that a server's decommission was carried out, gone with the request
    path "objects/rec/snapshot/*" { capabilities = ["write", "read", "list"] }   # its own snapshot shards: it never had this grant, and nobody noticed
    path "objects/rec/controller/pass" { capabilities = ["write", "read"] }   # its pass report, where /metrics reads rec_units_unplaced (the ninth review: a 403 every pass)
    path "objects/*"       { capabilities = ["read", "list"] }
    # WHAT IT READS, NOT EVERYTHING (М10's eighth review): it had `path "*"`, which read `secrets/vms` too — the key
    # the console's policy says only three jobs read. The rows it places from, the other subsystem's rows its
    # placement asks about — a server's labels from the console (`rec/servers/*`, feedback DQ) among them — the
    # heartbeats and snapshots, the platform's rows (`drain`, `schema`); never `secrets/*`,
    # never `domain/*`. `tests/test_policies.py` checks every read the code makes against this list.
    path "rec/*"           { capabilities = ["read", "list"] }
    path "vms/*"           { capabilities = ["read", "list"] }   # the cameras its recordings follow (`near`)
    path "platform/*"      { capabilities = ["read", "list"] }
  }
}
