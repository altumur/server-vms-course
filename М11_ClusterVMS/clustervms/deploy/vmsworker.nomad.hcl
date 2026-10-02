# deploy/vmsworker.nomad.hcl — the worker: DriverPack as a service job. It
# HOLDS the camera — one connection, one epoch, one fan-out (rtsp://<server>:
# 8554/<cam>) that the recorder, the gateway and the detectors subscribe to —
# and writes the camera's events into the resource on its server. It records
# nothing: footage is recworker.nomad.hcl's, the job with the disks.
# count = N and NOTHING in the VMS decides N: the operator sets the bounds,
# the Nomad Autoscaler moves count from the workers' own load. Each
# allocation claims slot w-<NOMAD_ALLOC_INDEX> by CAS on a Variable — the
# index is the preference, the Variable is the proof (Lesson 2).
job "vmsworker" {
  datacenters = ["room-a"]
  type        = "service"

  group "vmsworker" {
    count = 2

    scaling {
      enabled = true
      min     = 1
      max     = 12                                   # the servers' budget: B + n·I from М9 Lesson 7
      policy {
        cooldown            = "5m"                   # longer than a failover, so a reschedule is not read as demand
        evaluation_interval = "1m"
        check "load" {
          source = "prometheus"
          query  = "avg(vms_worker_load)"            # assigned ÷ capacity, from the heartbeats — never CPU
          strategy "target-value" { target = 0.9 }
        }
      }
    }

    # a worker writes its camera's EVENTS into the resource on its own server (as a detector does): only
    # servers that have one. Footage is not its concern — that constraint is the recorder's.
    constraint {
      attribute = "${meta.archive}"
      operator  = "is_set"
    }
    # spread, not distinct_hosts: Nomad puts workers on different servers when it can and doubles up when
    # it must (a dead server's worker rescheduled onto a neighbour). Whether a second worker on one server
    # CARRIES cameras is the administrator's choice on the console, not the scheduler's — `vms/policy
    # {servers: shared | distinct}`: shared (the default: a worker holds a camera, and several on one server
    # hold different cameras) a dead server's worker comes back on a neighbour with its cameras; distinct,
    # one worker per server carries cameras, a doubled-up worker idles by policy, and the CONTROLLER moves
    # a dead server's cameras (two silences: the slot lapsed and the server's resource silent). Both
    # readable in every placement reason. The recorder's own knob is rec/policy, distinct by default.
    spread {
      attribute = "${node.unique.id}"
    }

    disconnect {                                     # Lesson 4: the defaults are wrong for a process that holds a camera
      lost_after           = "45s"
      replace              = true
      stop_on_client_after = "25s"                   # the holder stops at TTL − margin on its own clock anyway
      reconcile            = "best_score"
    }

    task "vmsworker" {
      driver = "podman"
      kill_timeout = "20s"                           # room to release the slot: scale-in says so, a crash cannot
      identity { env = true }                        # NOMAD_TOKEN: the task's own workload identity, scoped by the policy
      config {
        image        = "localhost/clustervms:latest"
        network_mode = "host"
        args         = ["python3", "-m", "cluster", "worker"]
        volumes      = ["/data/archive:/data/archive", "/data/media:/data/media", "/run/vms:/run/vms"]   # it writes events, never footage; /run/vms: the tee's shared-memory branch for subscribers on this server
      }
      # The cluster's key (`w2cplatform/sealing.py`): rendered from the Nomad variable `secrets/vms` into this
      # task's secrets directory, which only this task sees. The policies let the console, the worker and the recorder read it
      # and no other job; the variable is `ring`: lines `<kid> <hex>`, the current key first.
      template {
        data        = "{{ with nomadVar \"secrets/vms\" }}{{ .ring }}{{ end }}"
        destination = "secrets/vms.key"
        perms       = "0600"
      }
      env {
        SECRETS_KEY = "/secrets/vms.key"         # what the template above rendered
        # The runtime's part of the seam (`w2cplatform/runtime.py`): the neutral names the loop
        # reads, filled here from Nomad's own. This file already knows the orchestrator — the
        # worker must not. A k8s manifest fills the same four from an ordinal and a fieldRef.
        SLOT_INDEX  = "${NOMAD_ALLOC_INDEX}"
        # The fan-out, OPENED: its default is loopback (М10B Lesson 4), and here a recorder or a gateway on
        # another server has to reach it. Nobody is asked who they are at this door — there is no
        # authentication below М12 — so this line is a statement about the network these servers are on: it
        # is closed to everybody else, or every camera's live stream is everybody's.
        RTSP_HOST   = "0.0.0.0"
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
        OBJECTS   = "variables://objects"          # heartbeats and the snapshot as Variables; no MinIO on this cluster
        CAPACITY  = "50"                             # this server's number; per node class in a product
        ARCHIVE   = "${meta.archive}"                # the label the constraint above placed by, handed to the worker: its events go there,
      }                                              # and it reports it in its heartbeat — the console's /servers shows the label beside the fact
      resources { cpu = 2000  memory = 2048 }        # B + n·I, rounded up
    }
  }
}
