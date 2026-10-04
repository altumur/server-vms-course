# deploy/nomad/recworker.nomad.hcl — the appendix «форма поставки»: the recorder as a Nomad service job. It writes
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
      user         = "vms"                           # a member of vms-recworker and of vms-obsd (gid 2101): the daemon lets it in
      kill_timeout = "40s"                           # the pipelines stop, the writer closes after its flush, then the hold goes
      config {
        command = "/opt/w2c/bin/w2c-run.sh"
        args    = ["recorder"]
      }
      env {
        PLATFORM_STORE  = "configstore:///run/configstore/recworker.sock"
        SLOT_INDEX      = "${NOMAD_ALLOC_INDEX}"
        INSTANCE_ID     = "${NOMAD_ALLOC_ID}"
        SERVER_NAME     = "${node.unique.name}"
        LABELS          = "${meta.labels}"
        BOX_ID          = "${node.unique.id}"        # which box: the node's id, the same across restarts
        OBSD_SOCKET     = "/run/vms-obsd/obsd.sock"  # where vms-obsd.service listens
        UNCONFIRMED_MAX = "90"
        SECRETS_KEY     = "/etc/w2c/secrets/platform.key"
        ARCHIVE      = "${meta.archive}"
        ARCHIVE_HOST = "${attr.unique.network.ip-address}"
        ARCHIVE_PORT = "8084"
        ARCHIVE_URL  = "http://${attr.unique.network.ip-address}:8084"
        OBJECTS   = "cluster:///data/platform/objects?resource=http://127.0.0.1:8090"
      }
      resources { cpu = 1000  memory = 1024 }
    }
  }
}
