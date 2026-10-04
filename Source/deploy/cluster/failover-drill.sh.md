# failover-drill.sh — the power pull on a real cluster, measured: three runs, the worst kept

**Role in the module.** Lesson 8, step 6. The stand proves the logic on a fake clock (`tests/cluster/test_lesson4_failover.py::test_the_power_pull`: nothing for 90 s, then the move by assignment); this script measures the number on three real servers. Run from the operator's machine with ssh to the servers and HTTP to a console: `deploy/cluster/failover-drill.sh srv-a 10.0.0.12:8080 3 [server|process]`.

## What a run does
1. Reads from the console's `/cameras` which cameras `w-<server>-1` holds, live (`held`).
2. Pulls. `server` (the default): every unit of the server is killed (SIGKILL) and stopped over ssh — the store's member, the resource, the console, the controllers, the workers — standing in for the power cut (an orderly stop would release the slot, and the cameras would move at once: that is a stop, not a failure). `process`: only the worker's process is killed; systemd starts the unit again in two seconds.
3. Waits, up to 240 s, until every one of those cameras is live again — on another worker (`server`) or under the same name (`process`) — and prints the wall-clock seconds (`where`).
4. `server`: starts the units again, waits 30 s, reads `vms_epoch_conflicts{worker="w-<server>-1"}` — the old instance fenced by the epochs at its first lease pass, its footage kept under its epoch, nothing moving back.
The worst of the runs is the datasheet number.

## What to expect
`server`: some 90 s and a pass — the slot is held 45 s after the last renewal, the margin past it 45 s more (`SLOT_LOST_AFTER`: what the dead process started may still be writing), then the controller's next pass on another server sees two silences (the slot out, the resource silent) and moves the cameras by assignment; the new holder takes the next epoch. A server whose resource is ALIVE and says the worker's process is not running moves at the slot's end, with no margin (`Controller.slot_fate`, the owner's decision of 3 October). `process`: two seconds of `RestartSec` and the restart's own claim; nothing moves.

## Notes
- No Nomad in it: the old script drained a node; with no orchestrator nothing restarts a process elsewhere, and the number is the controller's, not a scheduler's.
- The console the script asks must be on another server than the one pulled.
