# deploy/recworker.nomad.hcl — the recorder: the fourth subsystem's worker
# and the ONLY job placed on top of the archive for footage. A worker holds the
# camera (one connection, one fan-out); a recorder subscribes to that fan-out
# and writes into the volume it holds — its server's own, or a declared one —
# through the host's obsd (`obsd.service`, the same unit as М10's box: host
# infrastructure, like podman.socket, not a job). count = N as for the
# worker: the operator's bounds, the Autoscaler's move; each allocation
# claims slot r-<NOMAD_ALLOC_INDEX> by CAS (Lesson 2, the same proof).
job "recworker" {
  datacenters = ["room-a"]
  type        = "service"

  group "recworker" {
    count = 2

    scaling {
      enabled = true
      min     = 1
      max     = 12                                   # ≤ the archive servers under `servers: distinct` — a 13th would idle by policy
      policy {
        cooldown            = "5m"
        evaluation_interval = "1m"
        check "load" {
          source = "prometheus"
          query  = "avg(rec_worker_load)"            # assigned ÷ capacity from the recorders' heartbeats — never disk I/O
          strategy "target-value" { target = 0.9 }
        }
        # The second demand, and the one `load` cannot see. A recorder holds ONE archive
        # (`servers: distinct` over `place_by: volume`), so an archive the operator declared and nobody
        # holds needs a PROCESS, not a busier one — and the recorders that exist may be perfectly loaded
        # while it sits unserved. `rec_volumes_unserved` is that count, published by the console beside
        # the rest; with several checks the Autoscaler takes the larger count, so whichever demand is
        # bigger wins and neither hides the other.
        #
        # Scale-IN is `load`'s alone: this check asks for at least as many processes as there are live
        # ones, so it never brings the count down — a spare is cheap and it is what makes the NEXT
        # archive get served in a pass instead of a deploy.
        # `rec_recorders_needed`, not `rec_volumes_unserved`: an archive nobody CAN take does not become
        # takeable by starting processes. A local volume declared for a server the scheduler puts no
        # recorder on would leave `unserved` at one for ever, and this check would then ask for one more
        # worker, and another, to the ceiling — each of them a spare that cannot help. The console
        # subtracts the spares, so one free process is proof the shortage is not a shortage of processes.
        #
        # Counting LIVE workers rather than the configured count matters for the same reason: an
        # allocation that cannot be placed leaves the query where it was instead of compounding.
        check "unserved-archives" {
          source = "prometheus"
          query  = "rec_workers_live + rec_recorders_needed"
          strategy "pass-through" {}
        }
      }
    }

    # a recorder writes its events into the resource on its own server and its footage through that server's
    # obsd: only servers that have both — `meta.archive` says so. This is the constraint that USED to be the
    # worker's reason for the archive; it is the recorder's now.
    constraint {
      attribute = "${meta.archive}"
      operator  = "is_set"
    }
    # `near: vms` in rec.subsystem.yaml: the rec controller prefers the recorder on the server whose worker holds the
    # camera — there it reads the worker's tee through shared memory (/run/vms) instead of the RTSP fan-out. An
    # affinity, never a filter: no room beside the worker and the recording goes elsewhere, over RTSP, and the
    # placement reason says so ("away from w-1 on srv-a (no room there)").
    # spread, not distinct_hosts: a dead server's recorder comes back on a neighbour — and idles there by
    # default, because `rec/policy {servers: distinct}`: a second recorder on the same disks is no second
    # place to record. The rec CONTROLLER moves the dead server's recordings to a server whose resource
    # answers (Lesson 4's two silences); the footage before the move stays in the old server's volume,
    # named unavailable on the timeline until the server returns — not lost.
    spread {
      attribute = "${node.unique.id}"
    }

    disconnect {
      lost_after           = "45s"
      replace              = true
      stop_on_client_after = "25s"
      reconcile            = "best_score"
    }

    task "recworker" {
      driver = "podman"
      kill_timeout = "40s"                           # SIGTERM: the pipelines stop, the writer closes after its flush (up to 30 s), then the hold goes
      identity { env = true }
      # THE ARCHIVE'S ENGINE, AS М10'S UNIT RUNS IT (the review's fourth pass, blocker 3). Every node runs М10's
      # `obsd.service` (`vmsserver/deploy/install-obsd.sh`): the daemon as `obsd`, its socket in /run/obsd, and only
      # the members of `vms-rec` — gid 2101, `obsd.sysusers` — let in. This job still mounted /run/vms and named no
      # socket: every recorder of the cluster looked for the daemon where it no longer was, its volume `away` for
      # ever, nothing recorded. Now: /run/obsd mounted, `OBSD_SOCKET` said, and the group — as the PRIMARY group of
      # the task's root, which the daemon counts as it counts a supplementary one (the peer's gid; a root without it
      # is refused). `tests/test_recorder_job.py` checks all three against the unit and the install files.
      #
      # STILL ROOT, AND SO /run/obsd's RIGHTS DO NOT STOP IT (М10's fifth review, Т-M2 — open, said here). Root in the
      # container is root on the host's paths it mounts, so the 0750 of /run/obsd keeps out the processes that do not
      # mount it (the holder, a vendor's DriverPack), not this one. The recorder cannot drop to a user of its own yet:
      # it writes its events into /data/archive, which the resource and the workers own as root; it reads the
      # workers' shared-memory sockets in /run/vms, which they create as root with no group to join; and the key Nomad
      # renders 0600 is root's. Each is a change on the other side (the archive's and /run/vms's owner group, the
      # template's `uid`), and until all three are made `user = "<uid>:2101"` here would only make it fail.
      user = "0:2101"
      config {
        image        = "localhost/clustervms:latest"
        network_mode = "host"                        # it subscribes to workers' RTSP fan-outs, on this server or elsewhere
        args         = ["python3", "-m", "cluster", "recorder"]
        volumes      = ["/data/archive:/data/archive", "/run/vms:/run/vms", "/run/obsd:/run/obsd"]   # its events, and its own volume's path (the daemon opens it); /run/vms: the workers' shared memory; /run/obsd: the daemon's socket — this job's alone; no /data/media: it never reads a camera
      }
      # The cluster's key (`w2cplatform/sealing.py`): a network volume's `access_secret` is sealed by the console to its
      # row, and the daemon takes credentials only as the volume's parameters — so the recorder, which mounts the
      # volume, opens it (М10's third review, blocker 3). Rendered from the Nomad variable `secrets/vms` into this task's
      # secrets directory, as for the console and the worker; without it the recorder handed the bucket the ciphertext.
      template {
        data        = "{{ with nomadVar \"secrets/vms\" }}{{ .ring }}{{ end }}"
        destination = "secrets/vms.key"
        perms       = "0600"
      }
      env {
        SECRETS_KEY = "/secrets/vms.key"         # what the template above rendered
        OBSD_SOCKET = "/run/obsd/obsd.sock"      # where obsd.service listens (`--socket`)
        # The runtime's part of the seam (`w2cplatform/runtime.py`): the neutral names the loop
        # reads, filled here from Nomad's own. This file already knows the orchestrator — the
        # worker must not. A k8s manifest fills the same four from an ordinal and a fieldRef.
        SLOT_INDEX  = "${NOMAD_ALLOC_INDEX}"
        # How long this process goes on RECORDING past a lease's end while Nomad's Variables do not answer
        # (М10A Lesson 6). On one box there is no ceiling: the store is a directory, and nobody else can be
        # given the camera. Here the store is on the network — a worker cut off from it may still hold the
        # camera's session while its successor cannot connect. Ninety seconds past the lease's end: longer
        # than `lost_after` (45 s) and the slot's TTL, so the recording does not stop before anybody has
        # been given the camera, and not for ever.
        UNCONFIRMED_MAX = "90"
        SERVER_NAME = "${node.unique.name}"
        LABELS      = "${meta.labels}"
        INSTANCE_ID = "${NOMAD_ALLOC_ID}"
        OBJECTS   = "variables://objects"
        CAPACITY  = "50"                             # recordings this server's disks and NIC can take — its own number
        ARCHIVE   = "${meta.archive}"                # the label the constraint placed by, handed to the recorder: its events; its own volume goes beside it, `/data/volume`
        ARCHIVE_HOST = "${attr.unique.network.ip-address}"   # what its archive door binds: the node's address
        ARCHIVE_PORT = "8084"
        ARCHIVE_URL  = "http://${attr.unique.network.ip-address}:8084"   # what the heartbeat says: an IP, as RESOURCE_URL is — no DNS between servers
      }
      resources { cpu = 1000  memory = 1024 }
    }
  }
}
