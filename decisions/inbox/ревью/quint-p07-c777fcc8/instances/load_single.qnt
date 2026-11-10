module load_single {
  import load_core(POLICY="single", NC=3, NW=2, HANG=false, DEADLINE=false, REARM=false, DEL=false).* from "../load_overlap"
}
