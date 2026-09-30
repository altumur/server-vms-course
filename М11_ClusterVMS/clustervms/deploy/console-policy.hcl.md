
- `path "secrets/vms" { capabilities = ["read"] }` — the cluster's key, read by this job's template. Granted to the console and the worker and to no other job: the key is not in the store it protects, and not in every process's reach.
