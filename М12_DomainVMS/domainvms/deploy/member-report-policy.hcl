# The token a member's agent uses IN THE DOMAIN HOLDER, when the domain cannot reach that member
# (`domain/uplink.py`). One policy per member, rendered with its name: it reads what the domain publishes
# for it, and writes its own report and nothing else — one writer per prefix, as everywhere. The agent's
# policy in its OWN cluster (`agent-policy.hcl`) is unchanged.
#
# Lesson 17: a camera that can reach only its RELAY gets this policy in the relay's cluster instead, with
# the `relay/` paths below in place of `domain/*` — it reads what the relay relayed, and writes its report,
# which the relay carries up in its bundle.
#
#   nomad acl policy apply -description "report of cam-SN4471" report-cam-SN4471 member-report-policy.hcl
#   (with MEMBER replaced by the member's name)
namespace "default" {
  variables {
    path "domain/*"                          { capabilities = ["read"] }            # keys, revoked, grants/<it>, pending/<it>, sources, mirrors, primaries, shared, holder
    path "objects/domain/shared"             { capabilities = ["read"] }            # the shared settings' document (Lesson 12)
    path "objects/domain/backup"             { capabilities = ["read"] }            # the domain's backup, on the members that keep it (Lesson 15)
    path "objects/domain/members/MEMBER/*"   { capabilities = ["read", "write", "destroy"] }   # its report, and only its own
    # in a relay's cluster (Lesson 17): what the relay relayed for it
    path "relay/*"                           { capabilities = ["read"] }
    path "objects/relay/*"                   { capabilities = ["read"] }
  }
}
