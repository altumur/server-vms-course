# The console: UI, API façade, the read model, TLS, token verification.
# Runs in EVERY cluster (a single-cluster customer has it with no domain);
# the domain holder's instance is the same image pointed at every
# cluster's stores. Stateless; count = 2; placed anywhere.

# The scrapers that are not on the node itself — a Prometheus — comma-separated: their own lane through a flood
# (`CONSOLE_MONITORS` below).
variable "monitors" {
  type    = string
  default = ""
}

job "console" {
  datacenters = ["*"]
  type        = "service"

  group "console" {
    count = 2

    network { port "https" { static = 8443 } }

    service {
      name     = "console"
      port     = "https"
      provider = "nomad"
      check { type = "http"; path = "/healthz"; interval = "10s"; timeout = "2s" }
    }

    task "console" {
      driver = "podman"
      config {
        image   = "vms/domainvms:latest"
        args    = ["python3", "-m", "domain.console"]
        # The directory of the box's own door (`DOMAIN_CONSOLE_UNIX` below): 0700 root on the host, made at boot by
        # `vms.tmpfiles` — the same directory the cluster's console keeps its socket in, another file in it.
        volumes = ["/run/vms-console:/run/vms-console"]
      }
      identity { env = true }    # reads vms/snapshot, vms/*/heartbeat and domain/*; forwards writes to the owning cluster
      template {
        data        = <<-EOT
          # One line per cluster the console aggregates. The cluster-level
          # console lists its own cluster only; the domain's lists all.
          CLUSTERS=north=nomad://nomad.north:4646|http://minio.north:9000/cluster-restore,south=nomad://nomad.south:4646|http://minio.south:9000/cluster-restore
          LOST_AFTER=45
          REFRESH_INTERVAL=5
          # WHAT THE CODE OPENS, THE JOB TURNS ON (М10's eighth review, minor: the reserve and the lanes were in the
          # code and not here, and Nomad's own check of `/healthz` failed under a flood from sixteen addresses). The
          # box's own door — `curl --unix-socket /run/vms-console/domain-console.sock http://console/healthz` on the
          # node, connections of its own whatever the port's flood. And the monitors' lane: this node's loopback and
          # address — where Nomad's check and a scraper on the node come from — and the scrapers named in `monitors`.
          DOMAIN_CONSOLE_UNIX=/run/vms-console/domain-console.sock
          CONSOLE_MONITORS=127.0.0.1,{{ env "attr.unique.network.ip-address" }},${var.monitors}
        EOT
        destination = "local/console.env"
        env         = true
      }
      resources { cpu = 500  memory = 256 }
    }
  }
}
