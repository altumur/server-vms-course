module load_single_nomerge {
  import load_core(POLICY="single_nomerge", NC=3, NW=2, HANG=false, DEADLINE=false, REARM=false, DEL=false).* from "../load_overlap"
}
