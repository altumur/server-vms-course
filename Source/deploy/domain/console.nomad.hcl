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
        args    = ["python3", "-m", "w2cplatform.domain.console"]
        # The directory of the box's own door (`DOMAIN_CONSOLE_UNIX` below): 0700 root on the host, made at boot by
        # `vms.tmpfiles` — the same directory the cluster's console keeps its socket in, another file in it.
        # …and this cluster's store and objects, as М11 lays them on the node: the configstore's socket of its role,
        # the objects of `cluster://` (the twelfth review, major 22 — the job pointed at a `nomad://` store that no
        # longer exists, and `open_vars` refused it at start).
        volumes = ["/run/vms-console:/run/vms-console", "/run/configstore:/run/configstore", "/data/platform/objects:/data/platform/objects"]
      }
      identity { env = true }    # reads vms/snapshot, vms/*/heartbeat and domain/*; forwards writes to the owning cluster
      template {
        data        = <<-EOT
          # One line per cluster the console aggregates. The cluster-level
          # console lists its own cluster only; the domain's lists all. Its own
          # cluster by this node's store and objects; another cluster's store is
          # not opened from here (a configstore has no remote reader): it is a
          # member that REPORTS (`name=report`, `domain/uplink.py`).
          # The domain holder's own cluster by the DOMAIN's socket (the thirteenth review, major 11, a sibling): this
          # console writes the domain's pending edits, topology, crossings and members — `domain/*` rows, which the
          # cluster console's role does not write.
          CLUSTERS=north=configstore:///run/configstore/domain.sock|cluster:///data/platform/objects?resource=http://127.0.0.1:8090,south=report
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
