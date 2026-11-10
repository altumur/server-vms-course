module load_single_dl_norearm {
  import load_core(POLICY="single", NC=3, NW=2, HANG=true, DEADLINE=true, REARM=false, DEL=false).* from "../load_overlap"
}
