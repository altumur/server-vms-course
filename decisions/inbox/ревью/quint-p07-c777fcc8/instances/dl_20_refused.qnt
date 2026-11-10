module dl_20_refused {
  import deadline_core(T=20, ONTIMEOUT="refused", RULE="naive", DS=Set(90), GW=100, LOST=false, MAXT=200, BOUND=150).* from "../door_deadline"
}
