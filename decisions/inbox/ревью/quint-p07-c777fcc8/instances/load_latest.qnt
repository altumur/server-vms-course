module load_latest {
  import load_core(POLICY="latest", NC=3, NW=2, HANG=false, DEADLINE=false, REARM=false, DEL=false).* from "../load_overlap"
}
