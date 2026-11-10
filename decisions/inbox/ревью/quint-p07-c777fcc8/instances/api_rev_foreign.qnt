module api_rev_foreign {
  import api_core(DOOR="put", IFMATCH=true, KEY=false, LATE=false, RULE="rev_moved", FOREIGN=true, FOREIGN_SAME=false).* from "../api_outcome"
}
