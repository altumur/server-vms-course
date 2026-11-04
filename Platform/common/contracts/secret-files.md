# The secret file placement contract

This English text is the source; the Russian translation `ru/contracts/secret-files.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5), addendum (13): one rule of several processes is a contract, not copies
in chapters; the stage C guesses S-005, DF-G01, the Architect's decision of 2026-10-23). The owner is lesson
[P/02](../../02-installer/spec/02.4-installer.norms.md), chapter 2.4 (the layout Н1.1, the commands `w2cctl secrets` Н1.9 and «domain
installation» Н3 — the installer puts both files; ADR-0083 addendum (29) item 9: the line names the owner lesson of the norm; the library by the contract is written by the session `common` of the generation). One placement rule for all secret
files on a box: the ring file ([the sealing contract](sealing.md) «Ring file» `mode`, `link`) and the domain recovery file
([the domain founding contract](domain-founding.md) «Root and recovery file» `place`, `mode`). Where each file is to
be and what its mode is — in the contract of that file; here — how the reader and the writer check the placement.

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

```yaml
file:      a secret file is a regular file; the file itself is a symbolic link or a special file (a directory, a socket, a device,
           FIFO): a refusal, the file is neither read nor written
dirs:      symbolic links in the directories of the path are resolved before the placement check: the rule «вне каталога …» and «НЕ внутри …»
           of the file contract compares the resolved path with the resolved paths of the forbidden directories
refuse:    a directory of the path that does not resolve (absent, no access, a link loop), or a resolved path in a forbidden directory —
           a refusal, nothing is read and nothing changes
mode:      the mode and the owner are the file contract; they are checked on the file itself at every read where the file contract says so
forbidden: the full list of forbidden directories («вне …», «НЕ внутри …» of the file contract) is given by the calling installation —
           the command that reads or writes the file names them as the resolved paths of its layout (PLATFORM_DIR, the directories
           of the store, of the objects and of their copies); the list is empty or a forbidden directory does not resolve — a refusal without reading and without
           changing the target; the layout is considered unchanged for the time of one operation (the stage C guess SF-G01/G02, the Architect's decision of 2026-10-23)
  daemon:   a daemon process that reads the file at every start checks the roots of its environment (the store directory with file://,
            the object root, the event root); -dir of the store daemon and the copy directories unknown to it are excluded by the installation
            (C08-RING-FORBIDDEN-ROOTS-01, the decision of «Спецификация домена»)
  layout:   the list is the directories existing by the layout: the store directory (-dir of the store; on the stand {data}/configstore),
            the object root ({data}/objects), the copy directories — only those set by the settings (set but unresolvable —
            a refusal, refuse above); unset copies do not enter the list and give no refusal; other directories (backup, backups)
            the list does not invent (STAND-FORBIDDEN-DIRS-01, the Architect's decision of 2026-10-27)
write:     a write is published whole — a temporary file in the same directory, then rename; an existing target is checked
           by the rules file and refuse before the write; «create once» (the recovery file, the ring key new) does not replace an existing target —
           a refusal; a new version of the file is created at once with the mode of the file contract (the ring 0640, the recovery file
           0600), and does not change the mode after the write (the stage C guess SF-G01/G02, the Architect's decision of 2026-10-23)
  once:    «create once» is an atomic rename without replacement (renameat2 RENAME_NOREPLACE on Linux, renamex_np
           RENAME_EXCL on macOS); the OS, the kernel or the FS do not support it — a refusal without a change of the target, the temporary file is deleted;
           there are no workarounds through an ordinary rename or link (the stage C guess SF-G04, the Architect's decision of 2026-10-23)
  temp:    the temporary file is created at once with the mode of the file contract (0640/0600); the owner and the umask are fixed before writing
           the secret bytes; after the write the rights are not widened (SF-G04)
```

## Vectors

There are no vectors: the placement of a file (a symbolic link, the mode, the owner) cannot be expressed by a TSV row — a layout test of the implementation and reading. (ADR-0083 addendum (32) item 2)
