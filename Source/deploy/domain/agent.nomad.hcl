# The domain agent: one per cluster. Its only right is to write domain/* in
# THIS cluster's Variables — the signer's public key set and the revocation
# list, copied from the domain holder. When the domain is unreachable it
# stops updating; the cluster's console and gateway keep verifying with the keys they have.
job "domain-agent" {
  datacenters = ["*"]
  type        = "service"

  group "agent" {
    count = 1
    task "agent" {
      driver = "podman"
      config {
        image   = "vms/domainvms:latest"
        args    = ["python3", "-m", "domain.agent"]
        # This cluster's store, by the agent's own socket (the twelfth review, major 22: `nomad://` is gone).
        volumes = ["/run/configstore:/run/configstore"]
      }
      identity { env = true }    # bound to agent-policy.hcl: domain/* and nothing else
      template {
        data        = <<-EOT
          CLUSTER={{ env "NOMAD_REGION" }}
          DOMAIN_CONFIG_URL=configstore:///run/configstore/domainagent.sock   # the domain holder's store: this one, in the holder's cluster
          PLATFORM_STORE=configstore:///run/configstore/domainagent.sock      # this cluster, written — by the agent's own socket
          SYNC_INTERVAL=30
          OBJECTS_URL=http://minio.{{ env "NOMAD_REGION" }}:9000/cluster   # this cluster's objects: where it says what it reaches
          # REACHES=vlan:cctv-a,vlan:cctv-b   the site's names for the networks it sees; unset: the host's interfaces
          # RELAY=1                          a relay: relays and bundles for the members the domain's topology names
        EOT
        destination = "local/agent.env"
        env         = true
      }
      resources { cpu = 50  memory = 64 }
    }
  }
}
