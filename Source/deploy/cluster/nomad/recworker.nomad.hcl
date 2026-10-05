# deploy/cluster/nomad/recworker.nomad.hcl — the appendix «форма поставки»: the recorder as a Nomad service job. It writes
# its footage into the volume it holds through the node's obsd (`vms-obsd.service`, host infrastructure like the
# configstore, not a job) and serves it at its archive door — the same installation and runner as
# `vms-recworker.service`. Placed only where a volume can be: `meta.archive`.
job "recworker" {
  datacenters = ["room-a"]
  type        = "service"

  group "recworker" {
    count = 2

    constraint {
      attribute = "${meta.archive}"
      operator  = "is_set"
    }
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
      driver       = "raw_exec"
      # No umask of its own (the agent's 0022 is handed on): the runner sets 0007, as a unit's UMask= — what it
      # writes in the setgid events archive and objects is the group's (the thirteenth review, major 13).
      user         = "vms"                           # its groups are the task's: `vms-nomad.sysusers` (the socket, vms-obsd, the key ring)
      kill_timeout = "40s"                           # the pipelines stop, the writer closes after its flush, then the hold goes
      config {
        command = "/opt/w2c/bin/w2c-run.sh"
        args    = ["vms", "recorder"]
      }
      env {
        PLATFORM_STORE  = "configstore:///run/configstore/recworker.sock"
        SLOT_INDEX      = "${NOMAD_ALLOC_INDEX}"
        INSTANCE_ID     = "${NOMAD_ALLOC_ID}"
        SERVER_NAME     = "${node.unique.name}"
        LABELS          = "${meta.labels}"
        BOX_ID          = "${node.unique.id}"        # which box: the node's id, the same across restarts
        OBSD_SOCKET     = "/run/vms-obsd/obsd.sock"  # where vms-obsd.service listens
        SECRETS_KEY     = "/etc/w2c/secrets/platform.key"
        # No RESOURCE_ROOT: its events go where the node's resource keeps them, `RESOURCE_ROOT` in /etc/w2c/w2c.env
        # (`/data/platform/events`) — `meta.archive` only says where disks are, which is what the constraint asks.
        ARCHIVE_HOST = "${attr.unique.network.ip-address}"
        ARCHIVE_PORT = "8084"
        ARCHIVE_URL  = "http://${attr.unique.network.ip-address}:8084"
        OBJECTS   = "cluster:///data/platform/objects?resource=http://127.0.0.1:8090"
      }
      resources { cpu = 1000  memory = 1024 }
    }
  }
}
