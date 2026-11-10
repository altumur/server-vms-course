module dl_90 {
  import deadline_core(T=90, ONTIMEOUT="unknown_reread", RULE="naive", DS=Set(90), GW=100, LOST=true, MAXT=200, BOUND=90).* from "../door_deadline"
}
