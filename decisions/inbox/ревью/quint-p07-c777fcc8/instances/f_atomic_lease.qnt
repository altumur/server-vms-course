module f_atomic_lease {
  import leader_core(NT=2, ATOMIC=true, LEASE=true).* from "../feed_leader"
}
