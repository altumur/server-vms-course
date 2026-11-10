module api_val_foreign {
  import api_core(DOOR="put", IFMATCH=true, KEY=false, LATE=false, RULE="value_eq", FOREIGN=true, FOREIGN_SAME=false).* from "../api_outcome"
}
