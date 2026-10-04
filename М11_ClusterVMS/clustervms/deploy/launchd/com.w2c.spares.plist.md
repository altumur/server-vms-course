# com.w2c.spares.plist — the spares script every minute, on a macOS server

**Role in the module.** Lesson 4. The twin of `w2c-spares[-<role>].timer`: `w2c-spares.sh recworker vmsworker` every 60 s (`StartInterval`), `SPARES_RUN=/opt/w2c/bin/w2c-run.sh`. The script reads the console's numbers and starts the spares this server can serve (`nohup`, a pid file each); it never stops one. Installed only by `install.sh --spares`.
