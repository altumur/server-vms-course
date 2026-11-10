module r_ctrl_dl {
  import stall_core(K=3, DEADLINE=3, PARSE="refuse", MARK=false, MANIFEST_UP=false, MAXT=20, LIM=4).* from "../read_stall"
}
