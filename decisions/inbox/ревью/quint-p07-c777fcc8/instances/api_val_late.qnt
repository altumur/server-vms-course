module api_val_late {
  import api_core(DOOR="put", IFMATCH=true, KEY=false, LATE=true, RULE="value_eq", FOREIGN=false, FOREIGN_SAME=false).* from "../api_outcome"
}
