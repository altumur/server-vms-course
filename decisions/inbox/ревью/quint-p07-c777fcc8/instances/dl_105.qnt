module dl_105 {
  import deadline_core(T=105, ONTIMEOUT="unknown_reread", RULE="naive", DS=Set(90), GW=100, LOST=true, MAXT=200, BOUND=105).* from "../door_deadline"
}
