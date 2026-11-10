module load_free_hang {
  import load_core(POLICY="free", NC=3, NW=2, HANG=true, DEADLINE=false, REARM=false, DEL=false).* from "../load_overlap"
}
