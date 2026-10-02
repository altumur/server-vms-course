# deploy/console.nomad.hcl — the console: the page and the API.
# A system job: one instance on every server that runs a resource, so that
# any server's :8080 is the console and nothing sits in front of it — no
# load balancer, no ingress; a person types any server's name, or a DNS
# name that resolves to all of them. It is stateless and holds no database:
# every instance reads the same raft and the same heartbeats, /events asks
# every live resource's event index and merges, and a retried POST is answered
# the same by whichever instance gets it because the Idempotency-Key is a
# Variable (vms/idem/*).
# Placed on servers that run a resource so that an operator's marks have a
# bucket to go into; drop the constraint and /marks answers 503 there.
#
# THE IMAGE IS A VARIABLE, and М12 is why. A cluster's console asks who is calling once the cluster's store
# holds a domain's key set (М10A Lesson 15) — and what checks a token is М12's code, which is not in this
# module's image. A cluster in a domain runs the same job from the domain's image:
#   nomad job run -var image=vms/domainvms:latest console.nomad.hcl
# With this module's image in a cluster that HAS a key set, the console answers 503 to everything: it cannot
# check, so it admits nobody. That is the gate failing shut, not a fault to work around.
variable "image" {
  type    = string
  default = "localhost/clustervms:latest"
}

job "console" {
  datacenters = ["room-a"]
  type        = "system"

  group "console" {
    constraint {
      attribute = "${meta.archive}"
      operator  = "is_set"
    }
    network {
      mode = "host"
      port "console" { static = 8080 }
    }
    task "console" {
      driver = "podman"
      identity { env = true }
      config {
        image        = var.image
        network_mode = "host"
        args         = ["python3", "-m", "cluster", "console"]
        # /run/vms-console: the directory of the console's unix socket — the box's own door (`CONSOLE_UNIX` below;
        # М10's sixth review). 0700 root on the host, made by `vms.tmpfiles` (`install-obsd.sh`), like /run/obsd.
        volumes      = ["/data/archive:/data/archive", "/run/vms-console:/run/vms-console"]
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
        SERVER_NAME = "${node.unique.name}"
        LABELS      = "${meta.labels}"
        INSTANCE_ID = "${NOMAD_ALLOC_ID}"
        OBJECTS      = "variables://objects"
        ARCHIVE      = "/data/archive"
        CONSOLE_PORT = "8080"
        # Who is "on the box" is whoever came through this socket — the emergency entry's own turns, and connections
        # of its own when the port is flooded. On a server: `curl --unix-socket /run/vms-console/console.sock
        # http://console/session …`, or `ssh -L 8080:/run/vms-console/console.sock`. A TCP peer of 127.0.0.1 is the
        # network's, like any other (`w2cplatform/access.py`, `is_local`).
        CONSOLE_UNIX = "/run/vms-console/console.sock"
        CLUSTER      = "room-a"
      }
      service {                                      # what the autoscaler scrapes, what М12's read model and a browser reach
        name = "vms-console"
        port = "console"
        tags = ["metrics"]
      }
      # MEMORY, COUNTED (М10's sixth review, a run: four `PUT …/mask` of 32 MiB took this task to its 128 MiB and it
      # was killed — by a token that held no grant at all). Two things changed: rights are asked before the body, so a
      # caller with no right to the unit is refused with nothing read; and `BLOBS_AT_ONCE` (2) blobs are read at a
      # time, each `CONSOLE_MAX_BLOB` (32 MiB) while it is read and again while it is stored. So the worst an
      # administrator of a unit can ask of this process is some 75 MiB of its own (the page, the heartbeats it reads)
      # and 2 × 2 × 32 MiB of blobs: 256. A site whose masks are kilobytes may lower `CONSOLE_MAX_BLOB` and this with it.
      resources { cpu = 300  memory = 256 }             # the page and the API; no event index here
    }
  }
}
