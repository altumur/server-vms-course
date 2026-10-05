# deploy/cluster/nomad/vmsworker.nomad.hcl — the appendix «форма поставки»: the worker as a Nomad service job, for a site
# where an orchestrator is justified (a rented cluster, М12 Lesson 8). It HOLDS the camera and writes its events
# into the resource on its node; the same installation and runner as `vms-vmsworker.service`. What Nomad adds is
# the one thing this module does without: it starts the worker again on ANOTHER node when its node is lost — so the
# name comes from the allocation's index (`SLOT_INDEX`), which moves with the allocation, and `lost_after` is the
# margin the controller would otherwise wait. Count is the operator's; no autoscaler (the spares script reads the
# same numbers on a server of this module).
job "vmsworker" {
  datacenters = ["room-a"]
  type        = "service"

  group "vmsworker" {
    count = 2

    # spread, not distinct_hosts: workers on different nodes when they can be, doubled up when they must.
    spread {
      attribute = "${node.unique.id}"
    }

    disconnect {                                     # the defaults are wrong for a process that holds a camera
      lost_after           = "45s"
      replace              = true
      stop_on_client_after = "25s"                   # the holder stops at TTL − margin on its own clock anyway
      reconcile            = "best_score"
    }

    task "vmsworker" {
      driver       = "raw_exec"
      # No umask of its own (the agent's 0022 is handed on): the runner sets 0007, as a unit's UMask= — what it
      # writes in the setgid events archive and objects is the group's (the thirteenth review, major 13).
      user         = "vms"                           # its groups are the task's: `vms-nomad.sysusers` (the socket, the key ring)
      kill_timeout = "20s"                           # room to release the slot: a stop says so, a crash cannot
      config {
        command = "/opt/w2c/bin/w2c-run.sh"
        args    = ["vms", "worker"]
      }
      env {
        PLATFORM_STORE  = "configstore:///run/configstore/vmsworker.sock"
        SLOT_INDEX      = "${NOMAD_ALLOC_INDEX}"     # the name moves with the allocation: w-<index>
        INSTANCE_ID     = "${NOMAD_ALLOC_ID}"
        SERVER_NAME     = "${node.unique.name}"
        LABELS          = "${meta.labels}"
        RTSP_HOST       = "0.0.0.0"
        SECRETS_KEY     = "/etc/w2c/secrets/platform.key"
        OBJECTS   = "cluster:///data/platform/objects?resource=http://127.0.0.1:8090"
      }
      resources { cpu = 2000  memory = 2048 }        # B + n·I, rounded up
    }
  }
}
