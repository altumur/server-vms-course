module cat_lock {
  import cat_core(WINDOW=false, REVALIDATE=false, LOCK=true, CRASH=false).* from "../catalogue_window"
}
