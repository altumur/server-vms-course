module dl_105_ok {
  import deadline_core(T=105, ONTIMEOUT="unknown_reread", RULE="naive", DS=Set(1, 90), GW=100, LOST=false, MAXT=200, BOUND=105).* from "../door_deadline"
}
