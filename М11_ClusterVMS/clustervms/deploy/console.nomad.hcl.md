
- `template` → `secrets/vms.key`, `SECRETS_KEY = "/secrets/vms.key"` — the cluster's key (М10A Lesson 18, `sealing.py`), rendered from the Nomad variable `secrets/vms` into the task's own secrets directory. Only the console and the worker jobs render it: the console seals device passwords on the way into the store, the worker opens them for the pipeline.
