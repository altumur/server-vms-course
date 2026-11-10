module api_pos_late {
  import api_core(DOOR="put", IFMATCH=true, KEY=false, LATE=true, RULE="positive_only", FOREIGN=true, FOREIGN_SAME=false).* from "../api_outcome"
}
