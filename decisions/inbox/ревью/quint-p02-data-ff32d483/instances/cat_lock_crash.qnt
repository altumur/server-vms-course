module cat_lock_crash {
  import cat_core(WINDOW=false, REVALIDATE=false, LOCK=true, CRASH=true).* from "../catalogue_window"
}
