module load_revguard {
  import load_core(POLICY="revguard", NC=3, NW=2, HANG=false, DEADLINE=false, REARM=false, DEL=false).* from "../load_overlap"
}
