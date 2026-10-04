# deploy/cluster/nomad/configstore.nomad.hcl — the appendix «форма поставки»: the store's member on every node, when a site
# runs Nomad anyway (a rented cluster, М12 Lesson 8). A SYSTEM job: one allocation per node, pinned there for as long
# as the node exists — exactly what `configstore.service` is on a server of this module. Nomad here is a supervisor
# and nothing more: the same installation (`install.sh`: /opt/w2c, the rights file, /etc/w2c/tls), the same runner,
# the same flags from /etc/w2c/w2c.env. Nomad's own Variables are not the store: the processes open the configstore's
# sockets, and the rights are the daemon's (no Variables ACL policies).
job "configstore" {
  datacenters = ["room-a"]
  type        = "system"

  group "configstore" {
    network {
      mode = "host"
      port "raft" { static = 8301 }
      port "api"  { static = 8300 }
    }
    task "configstore" {
      driver = "raw_exec"                            # the host's own process: its journal and its sockets are the host's
      config {
        command = "/opt/w2c/bin/w2c-run.sh"
        args    = ["configstore"]
      }
      kill_timeout = "20s"
      resources { cpu = 300  memory = 256 }
    }
  }
}
