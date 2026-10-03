# deploy/resource-policy.hcl — bound to job resource's workload identity.
# The platform's resource writes its own heartbeat and reads the mirror
# knob and every subsystem's retention rows. It never writes any
# subsystem's configuration. Mirrors go resource to resource over HTTP,
# not through any store.
namespace "default" {
  variables {
    path "objects/platform/resources/*" { capabilities = ["write", "read", "list"] }
    path "platform/mirror"              { capabilities = ["read"] }
    # Where each resource answers for its server's objects (`platform/doors/<server>`): its own row written at start,
    # the others read when somebody asks for the cluster's objects (`/v1/objects?scope=cluster`).
    path "platform/doors/*"             { capabilities = ["write", "read", "list"] }
    # The watermark's settings (М10A Lesson 14). The pass has read this row since there was a watermark, and
    # the grant was missing: nothing noticed while the watermark was off unless a row said otherwise. It is on
    # by default now, and a resource that may not read its settings must not be left guessing them.
    path "platform/space"               { capabilities = ["read"] }
    path "*/retention"                  { capabilities = ["read"] }
    path "*/retention/*"                { capabilities = ["read"] }
    path "*/alarms_retention"           { capabilities = ["read"] }   # the alarms' own days (М10A Lesson 12): their tree is swept by these
    path "*/alarms_retention/*"         { capabilities = ["read"] }
    path "rec/recordings/*"             { capabilities = ["read", "list"] }   # a recording's row: which camera it records, for the buckets a keep holds
    # What somebody said to keep (М10B Lesson 18). The pass reads these BEFORE it deletes anything, and a
    # pass that cannot read them does not run: without this grant retention stops, loudly, on every box.
    path "rec/keeps/*"                  { capabilities = ["read", "list"] }
    path "platform/schema"      { capabilities = ["read"] }   # the store's schema, checked first (`check_schema`; М10's eighth review)
  }
}
