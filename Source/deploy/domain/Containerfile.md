# Containerfile — `vms/domainvms:latest`: М11's image plus `domain/` and the signing library

**Role.** The image every job in this module's `deploy/*.nomad.hcl` names, and — the part that was missing — the image a **cluster's own console** runs from once the cluster is in a domain. Until this file existed the image was referred to and never built.

**Why a cluster's console needs it.** The console's gate (М10A Lesson 15, step 12а) asks who is calling as soon as the cluster's store holds a domain's key set. The platform has the gate and no cryptography; the check is `domain.access.ClusterAccess` (Lesson 4, step 6). М11's image contains neither `domain/` nor `cryptography`, so a console left on it in a domain answers 503 to everything — shut, as designed, and useless. The console job in М11 takes its image as a variable for exactly this: `nomad job run -var image=vms/domainvms:latest console.nomad.hcl`.

## Instructions
- `FROM localhost/clustervms:latest` — М11's image: `w2cplatform/`, `vms/`, `gstvms/`, `cluster/` under `/app`.
- `RUN apt-get … python3-cryptography` — Ed25519 and X.509: what `domain/tokens.py` verifies with and `domain/signer.py` issues with. From the distribution, not from `pip`: the base is Debian, and the box has no registry.
- `COPY domain domain` — this package, to `/app/domain`. Tests and deploy files stay out.
- `ENV ACCESS_IMPL=domain.access:cluster_access` — what the gate loads. It is the default in the code too; said here so that the image states what it is for.
- `CMD ["python3", "-m", "domain.agent"]` — the default verb; every jobspec overrides it.

**Not verified here.** The image was not built on the course's machine: there is no container runtime on it. `tests/domain/test_cluster_console_gate.py` checks what the file promises — that it copies `domain` and installs the library — and that the gate works with the module present; it does not run a container.
