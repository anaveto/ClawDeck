#!/usr/bin/env bash
# Test only: how long Wine's cabinet.dll lookup takes, and whether a new prefix's system32 holds the same PE file
set -u
unset TMPDIR
t() { local s=$(date +%s.%N); "$@"; echo "  took $(echo "$(date +%s.%N) - $s" | bc) s"; }
echo "find /usr /opt (merged #207):"; t find /usr /opt -path '*/wine/x86_64-windows/cabinet.dll' 2>/dev/null
echo "find /usr/lib* /usr/local/lib* /opt -maxdepth 5:"; t find /usr/lib* /usr/local/lib* /opt -maxdepth 5 -path '*/wine/x86_64-windows/cabinet.dll' 2>/dev/null
export WINEPREFIX=$(mktemp -d)/prefix WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="
s=$(date +%s); timeout 120 wine cmd /c echo ready 2>/dev/null; echo "first start: $(( $(date +%s) - s )) s"
sys=$WINEPREFIX/drive_c/windows/system32/cabinet.dll
dir=$(find /usr/lib* /usr/local/lib* /opt -maxdepth 5 -path '*/wine/x86_64-windows/cabinet.dll' 2>/dev/null | head -1)
ls -la "$sys" "$dir"; sha256sum "$sys" "$dir"
cmp -s "$sys" "$dir" && echo "system32 copy: identical" || echo "system32 copy: DIFFERENT"
