module ba_follow {
  import backoff_core(PERIOD=5, RA=10, FOLLOW=true).* from "../read_backoff"
}
