module c_dur1 {
  import conn_core(NT=2, L=2, PICK="fifo", TIMER="call", MAX_HELD=-1, DUR=1, CALLS=Set(1), OFFSETS=Set(15), WAIT=15, GAP=1, DEADLINE=20).* from "../conn_limit"
}
