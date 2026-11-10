module r_ctrl_parse {
  import stall_core(K=3, DEADLINE=-1, PARSE="refuse", MARK=false, MANIFEST_UP=false, MAXT=20, LIM=4).* from "../read_stall"
}
