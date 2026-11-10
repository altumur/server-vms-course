module dl_95 {
  import deadline_core(T=95, ONTIMEOUT="unknown_reread", RULE="naive", DS=Set(90), GW=100, LOST=true, MAXT=200, BOUND=95).* from "../door_deadline"
}
