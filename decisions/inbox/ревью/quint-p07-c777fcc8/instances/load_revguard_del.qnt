module load_revguard_del {
  import load_core(POLICY="revguard", NC=3, NW=2, HANG=false, DEADLINE=false, REARM=false, DEL=true).* from "../load_overlap"
}
