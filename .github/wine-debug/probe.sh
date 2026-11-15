#!/usr/bin/env bash
# Test only: where the first start of a fresh Wine prefix waits. Starts it in the background with Wine's process,
# boot and error channels on, then lists every process (with its WINEPREFIX) at 30, 90 and 330 s, the time Wine's
# boot wait gives up (5 min), and lets `wineserver -w` wait at most 60 s.
set -u
unset TMPDIR
work=$(mktemp -d); export WINEPREFIX="$work/prefix" WINEDLLOVERRIDES="cabinet=n,b;mscoree,mshtml="
export WINEDEBUG="+process,+loaddll,+wineboot,+setupapi,err+all,warn+all,fixme-all"
wine --version; echo "wine: $(command -v wine) wineserver: $(command -v wineserver || echo none) DISPLAY=${DISPLAY:-unset} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-unset} uid=$(id -u)"
plist() {
  echo "=== $1 s: processes"
  ps -eo pid,ppid,etimes,stat,wchan:20,args --forest | grep -v -E "ps -eo|grep -v" | cut -c1-220
  echo "=== $1 s: processes with this WINEPREFIX"
  for p in /proc/[0-9]*; do
    tr '\0' '\n' < $p/environ 2>/dev/null | grep -qxF "WINEPREFIX=$WINEPREFIX" && echo "$(basename $p) $(tr '\0' ' ' < $p/cmdline | cut -c1-150)"
  done
  echo "=== $1 s: last log lines"; tail -n 15 "$work/wine.log" | cut -c1-250
}
start=$(date +%s)
( wine cmd /c echo Wine prefix ready > "$work/out.txt" 2> "$work/wine.log"; echo "exit $? after $(( $(date +%s) - start )) s" >> "$work/out.txt" ) &
for t in 30 90 330; do sleep $(( t - ($(date +%s) - start) )); plist $t; cat "$work/out.txt"; done
echo "=== log lines that name wineboot, timeouts, errors (first 80)"
grep -n -i -E "wineboot|timed out|timeout|err:|starting|exit_process|create_process" "$work/wine.log" | head -n 80 | cut -c1-250
echo "=== wineserver -w, at most 60 s"
ws=$(command -v wineserver || true)
if [ -z "$ws" ]; then for pid in $(pgrep wineserver); do ws=$(readlink /proc/$pid/exe); break; done; fi
s=$(date +%s); timeout 60 "$ws" -w; echo "wineserver -w: status $? after $(( $(date +%s) - s )) s"
plist "after -w"
echo "=== log size $(wc -l < "$work/wine.log") lines"
