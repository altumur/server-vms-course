# The same one-writer-per-prefix pattern М11's policies enforce for the VMS:
# a worker may write vms/<w>/* and its slot, the controller vms/*; the agent
# may write domain/*; nobody else.
namespace "default" {
  variables {
    # Everything the agent carries is under domain/: keys, revoked, grants (Lesson 4), pending and outcomes
    # (Lesson 9), sources, mirrors and primaries (Lessons 13–14), the shared settings' pointer and the holder
    # (Lessons 12, 15). One prefix, so one line — it listed the first three only and lagged every lesson after.
    path "domain/*"         { capabilities = ["read", "write"] }
    # its objects: the verified copies of the domain's documents (Lessons 12, 15) and `domain/seen`, when it
    # last reached the domain (Lesson 13) — on a camera that store is RAM for what changes every pass
    path "objects/domain/*" { capabilities = ["read", "write"] }
    # Lesson 17, a relay that is its cameras' only road to the domain: what the domain left for them, relayed
    # down into this cluster (`chain.relay`), and the time this relay last reached the domain.
    path "relay/*"          { capabilities = ["read", "write"] }
    path "objects/relay/*"  { capabilities = ["read", "write"] }
    path "vms/*"            { capabilities = ["deny"] }
  }
}
