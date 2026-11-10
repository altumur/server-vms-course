// C4: the cost of one cycle `order`, counted from the list (nr:49, nr:50, nr:53, nr:195, nr:57, nr:230-231 holder mode).
// A deterministic walk over the steps of the order, one request per step, for given sizes. A count of the text, not a measure of a module.
// S: subsystems whose units are loaded; SC: subsystems of the catalogue; PF: loaded catalogue profiles beside the root; F: 1 if a subsystem declares folders; PG: pages of /domain; SH: shared subsystems.
// M: feed messages during the poll period: each is the same full load (nr:57).
module cost_core {
  const S: int
  const SC: int
  const PF: int
  const F: int
  const PG: int
  const SH: int
  const M: int
  val cycle = 3 + S + F + 1 + PF + SC + SH + 2 + PG + 1 + 1 + 1
  // session, manifest, mounts; rows; folders; /servers root; other profiles; unplaceable (all of the catalogue); shared; drain, schema; pages of /domain; alarms; held; metrics
  var phase: int
  var req: int
  action init = all { phase' = 0, req' = 0 }
  action advance = all {
    phase < (M + 1) * cycle,
    phase' = phase + 1,
    req' = req + 1,
  }
  action stutter = all { phase >= (M + 1) * cycle, phase' = phase, req' = req }
  action step = any { advance, stutter }
  val inv_req_expected = (phase >= (M + 1) * cycle) implies req == (M + 1) * (3 + S + F + 1 + PF + SC + SH + 2 + PG + 1 + 1 + 1)
  val wit_done = not(phase >= (M + 1) * cycle)
}
