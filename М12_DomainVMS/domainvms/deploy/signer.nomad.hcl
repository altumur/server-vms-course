# The domain signer: one job, two keys (the CA and the token issuer), in the
# DOMAIN HOLDER only. count = 1 is not exactly-one during a reschedule, and
# that is harmless here: same key, same signatures. The key lives in the
# Variable domain/signer — a software key on purpose; a TPM would pin the
# job to one server and defeat the failover it just gained.

# The scrapers that are not on the node itself, comma-separated (`CONSOLE_MONITORS` below).
variable "monitors" {
  type    = string
  default = ""
}

job "domain-signer" {
  region      = "north"          # the domain holder: a stated decision, recorded where the directory can report it
  datacenters = ["*"]
  type        = "service"

  group "signer" {
    count = 1

    # What the operator may say: a CONSTRAINT, never a server.
    constraint {
      attribute = "${meta.role}"
      operator  = "!="
      value     = "worker"       # not on a server carrying fifty cameras (meta.role, set in client.hcl)
    }

    network { port "https" {} }

    service {
      name     = "domain-signer"
      port     = "https"
      provider = "nomad"
    }

    task "signer" {
      driver = "podman"
      config {
        image   = "vms/domainvms:latest"
        args    = ["python3", "-m", "domain.signer_service"]
        # The box's own door's directory (`SIGNER_UNIX` below); this cluster's store and objects (the twelfth review,
        # major 22: `nomad://` is gone).
        volumes = ["/run/vms-console:/run/vms-console", "/run/configstore:/run/configstore", "/data/platform/objects:/data/platform/objects"]
      }
      identity { env = true }    # NOMAD_TOKEN: may write domain/signer, identity/*, domain/keys, domain/revoked, and the books
      template {
        data        = <<-EOT
          DOMAIN_ID=acme
          OBJECT_STORE_URL=http://minio.north:9000/domain
          TOKEN_LIFETIME=900
          IDENTITY_PUBLISH_FLOOR=60
          # The books (domain/books.py): sources, primaries, polls, upstream, asks — they carry tokens this
          # job mints, so their pass runs here. The same list as the domain's console; CENTRE/STAR, Lesson 17.
          CLUSTERS=north=configstore:///run/configstore/console.sock|cluster:///data/platform/objects?resource=http://127.0.0.1:8090,south=report
          LOST_AFTER=45
          # The box's own door to the door in (`/login` through a flood, from the node: `--unix-socket`), and the
          # monitors' lane for `/healthz` (М10's eighth review: in the code, and not turned on here).
          SIGNER_UNIX=/run/vms-console/signer.sock
          CONSOLE_MONITORS=127.0.0.1,{{ env "attr.unique.network.ip-address" }},${var.monitors}
        EOT
        destination = "local/signer.env"
        env         = true
      }
      resources { cpu = 200  memory = 128 }
    }
  }
}
