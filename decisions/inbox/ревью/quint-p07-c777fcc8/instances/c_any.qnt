module c_any {
  import conn_core(NT=2, L=2, PICK="any", TIMER="call", MAX_HELD=-1, DUR=1, CALLS=Set(1), OFFSETS=Set(15), WAIT=15, GAP=0, DEADLINE=20).* from "../conn_limit"
}
