# The token a member's agent uses IN THE DOMAIN CLUSTER, when the domain cannot reach that member
# (`domain/uplink.py`). One policy per member, rendered with its name: it reads what the domain publishes
# for it, and writes its own report and nothing else — one writer per prefix, as everywhere. The agent's
# policy in its OWN cluster (`agent-policy.hcl`) is unchanged.
#
# Lesson 17: a camera that can reach only its OFFICE gets this policy in the office's cluster instead, with
# the `relay/` paths below in place of `domain/*` — it reads what the office relayed, and writes its report,
# which the office carries up in its bundle.
#
#   nomad acl policy apply -description "report of cam-SN4471" report-cam-SN4471 member-report-policy.hcl
#   (with MEMBER replaced by the member's name)
namespace "default" {
  variables {
    path "domain/*"                          { capabilities = ["read"] }            # keys, revoked, grants/<it>, pending/<it>, sources, mirrors, primaries, shared, host
    path "objects/domain/shared"             { capabilities = ["read"] }            # the shared settings' document (Lesson 12)
    path "objects/domain/backup"             { capabilities = ["read"] }            # the domain's backup, on the members that keep it (Lesson 15)
    path "objects/domain/members/MEMBER/*"   { capabilities = ["read", "write", "destroy"] }   # its report, and only its own
    # in an office's cluster (Lesson 17): what the office relayed for it
    path "relay/*"                           { capabilities = ["read"] }
    path "objects/relay/*"                   { capabilities = ["read"] }
  }
}
