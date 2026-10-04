# vms.env.example — `/etc/vms/vms.env`, the VMS subsystem's settings of a cluster server

**Role in the module.** Lesson 3. The subsystem's half of the split: `ARCHIVE` (the resource's tree; a recorder's own volume beside it), `SHM_DIR`, `CAPACITY` (measured on this server), the ports, the recorder's archive door (`ARCHIVE_URL`, `ARCHIVE_HOST` — an address, no DNS between servers), `CONSOLE_MONITORS` (the addresses that scrape, never a network), `CLUSTER`. On the data partition (`/data/vms/etc`, `/etc/vms` a link to it). Read by `w2c-run.sh` after `w2c.env`, under both it and the unit.
