module load_single_dl_rearm {
  import load_core(POLICY="single", NC=3, NW=2, HANG=true, DEADLINE=true, REARM=true, DEL=false).* from "../load_overlap"
}
