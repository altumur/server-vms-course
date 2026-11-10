// M4: publication of the rights file and of the manifest get files by atomic rename without a barrier.
// Anchors (slice ff32d483):
//   25:184    the rights file: the atomic rename of the candidate over the installed file
//   24:457    manifest get: each file by its own atomic rename over the name
//   24:28     Q2 barriers are named only for secrets and recovery files (this is why M4 is about the others)
//   p012:241  a rights file with an unknown field or absent: start of the store refused, code 2 (the outcome of a bad file)
// A rename is atomic in the file system's namespace; the text says nothing about durability. Crash semantics are a parameter:
// FS_EMPTY = true: after a crash the renamed name may hold the new inode without its data (the classic empty-file-after-crash ordering,
// POSIX does not exclude it). FS_EMPTY = false: such an ordering does not occur on this file system. Neither is a claim about a real FS.
// BARRIER_DATA / BARRIER_DIR: control — fsync of the file before rename, fsync of the directory after it.
module pub_core {
  const FS_EMPTY: bool
  const BARRIER_DATA: bool
  const BARRIER_DIR: bool

  var phase: str          // tmp | synced | renamed | dirsynced | done
  var dataDurable: bool
  var renameDurable: bool
  var reported: bool      // the writer reported success
  var after: str          // "" (no crash yet) | "old" | "new" | "empty"

  action init = all {
    phase' = "tmp", dataDurable' = false, renameDurable' = false, reported' = false, after' = "",
  }

  action sync = all {
    after == "",
    BARRIER_DATA, phase == "tmp",
    phase' = "synced", dataDurable' = true,
    renameDurable' = renameDurable, reported' = reported, after' = after,
  }

  action rename = all {
    after == "",
    phase == "synced" or (not(BARRIER_DATA) and phase == "tmp"),
    phase' = "renamed",
    dataDurable' = dataDurable, renameDurable' = renameDurable, reported' = reported, after' = after,
  }

  action dirSync = all {
    after == "",
    BARRIER_DIR, phase == "renamed",
    phase' = "dirsynced", renameDurable' = true,
    dataDurable' = dataDurable, reported' = reported, after' = after,
  }

  action report = all {
    after == "",
    (phase == "renamed" and not(BARRIER_DIR)) or phase == "dirsynced",
    phase' = "done", reported' = true,
    dataDurable' = dataDurable, renameDurable' = renameDurable, after' = after,
  }

  // A power loss at any point. What the disk keeps:
  action crash = {
    nondet d = oneOf(Set(true, false))
    nondet r = oneOf(Set(true, false))
    all {
      after == "",
      val dataKept = dataDurable or (phase != "tmp" and d)
      val renameKept = renameDurable or (phase != "tmp" and phase != "synced" and r)
      val out = if (not(renameKept)) "old"
                else if (dataKept) "new"
                else if (FS_EMPTY) "empty" else "old"
      all {
        after' = out, phase' = phase, dataDurable' = dataDurable, renameDurable' = renameDurable, reported' = reported,
      }
    }
  }

  action stutter = all {
    after != "", phase' = phase, dataDurable' = dataDurable, renameDurable' = renameDurable, reported' = reported, after' = after,
  }

  action step = any { sync, rename, dirSync, report, crash, stutter }

  val inv_no_empty_after_crash = after != "empty"
  val inv_reported_survives = not(reported) or after == "" or after == "new"
  val wit_empty_file_after_crash = not(after == "empty" and renameDurable == false)
  val wit_lost_publication = not(reported and after == "old")
  val wit_normal_publish = not(reported and after == "new")
}
