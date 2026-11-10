module load_free {
  import load_core(POLICY="free", NC=3, NW=2, HANG=false, DEADLINE=false, REARM=false, DEL=false).* from "../load_overlap"
}
