module r_ctrl_mark {
  import stall_core(K=3, DEADLINE=3, PARSE="refuse", MARK=true, MANIFEST_UP=false, MAXT=20, LIM=4).* from "../read_stall"
}
