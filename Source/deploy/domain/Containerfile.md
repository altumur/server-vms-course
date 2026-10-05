# Containerfile — `vms/domainvms:latest`: М11's image plus the library the domain signs with

**Role.** The image for a site that runs the domain's processes in containers (a quadlet beside `deploy/domain/systemd`'s units, the same `w2c-run.sh` verbs), and the image a cluster's own console runs from once the cluster is in a domain: the console's gate loads `w2cplatform.domain.access` to check a token, which needs `cryptography`. The domain's code is the platform's (`w2cplatform/domain`, `w2cplatform/trust`) and the VMS's part is `vms/domainpart` — both already in М11's image; this one adds `python3-cryptography` (from the distribution, not from `pip`) and the default verb `python3 -m w2cplatform.domain.agent`. `SPEC_DIR=/app/vms`: the specs whose `domain:` sections the domain reads.

**Not verified here.** The image was not built on the course's machine; `tests/domain/test_cluster_console_gate.py` checks what the file promises.
