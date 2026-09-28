# deploy/vmsworker-policy.hcl — bound to job vmsworker's workload identity.
# A worker writes its epochs (by CAS, when it starts a camera), its slot
# (by CAS, when it claims a name) and what a device it holds can say and do,
# and nothing else. verify-bench.sh proves
# the "nothing else" from inside an allocation.
namespace "default" {
  variables {
    path "vms/epoch/*"  { capabilities = ["write", "read", "list"] }
    path "vms/slots/*"  { capabilities = ["write", "read", "list"] }
    path "vms/holds/*"  { capabilities = ["write", "read", "list"] }    # the place it took — a claim about this process, like its slot
    path "vms/devices/*" { capabilities = ["write", "read", "list"] }   # what a device it holds turned out to be (М10B Lesson 25)
    path "objects/vms/heartbeats/*" { capabilities = ["write", "read", "list"] }   # its heartbeat, as an object-as-Variable
    path "objects/vms/*" { capabilities = ["read", "list"] }            # the snapshot and the blobs: read, never written by a worker
    path "vms/*"        { capabilities = ["read", "list"] }
  }
}
