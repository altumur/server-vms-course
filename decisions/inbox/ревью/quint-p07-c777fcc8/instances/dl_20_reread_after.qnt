module dl_20_reread_after {
  import deadline_core(T=20, ONTIMEOUT="unknown_reread", RULE="afterdl", DS=Set(90), GW=100, LOST=true, MAXT=200, BOUND=150).* from "../door_deadline"
}
