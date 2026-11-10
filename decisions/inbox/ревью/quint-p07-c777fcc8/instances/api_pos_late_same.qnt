module api_pos_late_same {
  import api_core(DOOR="put", IFMATCH=true, KEY=false, LATE=true, RULE="positive_only", FOREIGN=true, FOREIGN_SAME=true).* from "../api_outcome"
}
