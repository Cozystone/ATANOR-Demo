#!/bin/sh
# ATANOR living wallpaper — firefox-esr runtime. (Debian's chromium renderer
# produced 0-byte DOM for every URL on this minbase image while firefox renders
# fine — measured, not assumed.) The surface becomes the DESKTOP layer itself.
ok=0
while [ "$ok" -lt 2 ]; do
  if curl -sf -m 4 http://127.0.0.1:3000/shell >/dev/null 2>&1; then ok=$((ok+1)); else ok=0; fi
  sleep 5
done
mkdir -p /tmp/ffwall
firefox-esr --kiosk --new-instance --profile /tmp/ffwall \
  "http://127.0.0.1:3000/shell?wallpaper=1" &
B=$!
WID=""
i=0
while [ $i -lt 120 ]; do
  WID=$(xdotool search --name 'ATANOR WALLPAPER' 2>/dev/null | head -1)
  [ -n "$WID" ] && break
  i=$((i+1)); sleep 1
done
if [ -n "$WID" ]; then
  xprop -id "$WID" -f _NET_WM_WINDOW_TYPE 32a \
    -set _NET_WM_WINDOW_TYPE _NET_WM_WINDOW_TYPE_DESKTOP
fi
wait $B
