# deploy/cluster/nomad/console.nomad.hcl — the appendix «форма поставки»: the console as a Nomad SYSTEM job, one on every
# node — any node's :8080 is the console, as with `vms-console.service`. Stateless: every instance reads the same
# store through its node's configstore.
#
# THE INSTALLATION IS A VARIABLE, and М12 is why. A cluster's console asks who is calling once the store holds a
# domain's key set (М10A Lesson 15), and what checks a token is М12's code, which is not in this module's
# installation. A cluster in a domain runs the same job from the domain's:
#   nomad job run -var w2c_home=/opt/w2c-domain console.nomad.hcl
# With this module's installation in a cluster that HAS a key set, the console answers 503 to everything: it cannot
# check, so it admits nobody. That is the gate failing shut, not a fault to work around.
variable "w2c_home" {
  type    = string
  default = "/opt/w2c"
}

# The addresses of the scrapers that are not on the node itself — Prometheus — comma-separated (`CONSOLE_MONITORS`).
variable "monitors" {
  type    = string
  default = ""
}

job "console" {
  datacenters = ["room-a"]
  type        = "system"

  group "console" {
    network {
      mode = "host"
      port "console" { static = 8080 }
    }
    task "console" {
      driver = "raw_exec"
      # No umask of its own (the agent's 0022 is handed on): the runner sets 0007, as a unit's UMask= — what it
      # writes in the setgid events archive and objects is the group's (the thirteenth review, major 13).
      user   = "vms"                                 # its groups are the task's: `vms-nomad.sysusers` (the socket, the key ring)
      config {
        command = "${var.w2c_home}/bin/w2c-run.sh"
        args    = ["console"]
      }
      env {
        W2C_HOME       = "${var.w2c_home}"
        PLATFORM_STORE = "configstore:///run/configstore/console.sock"
        SERVER_NAME    = "${node.unique.name}"
        SECRETS_KEY    = "/etc/w2c/secrets/platform.key"
        OBJECTS        = "cluster:///data/platform/objects?resource=http://127.0.0.1:8090"
        CONSOLE_PORT   = "8080"
        CONSOLE_UNIX   = "/run/vms-console/console.sock"
        # Who scrapes /metrics with its own connections: this node's loopback and address, and what `monitors` names.
        CONSOLE_MONITORS = "127.0.0.1,${attr.unique.network.ip-address},${var.monitors}"
        CLUSTER        = "room-a"
      }
      service {
        name = "vms-console"
        port = "console"
        tags = ["metrics"]
      }
      resources { cpu = 300  memory = 256 }
    }
  }
}
