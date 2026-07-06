#!/bin/sh
# The resident orb: a floating, undecorated, always-on-top window over the
# ATANOR desktop. MOTIF hints strip the titlebar (openbox honors them);
# wmctrl pins above+sticky. The window is the SAME /shell surface as the app.
# STABLE web, not just alive: at first boot the web unit cycles with the engine
# (Requires=), and a surface launched into a down-window keeps an error page
# forever. Two consecutive 200s five seconds apart = actually up.
ok=0
while [ "$ok" -lt 2 ]; do
  if curl -sf -m 4 http://127.0.0.1:3000/shell >/dev/null 2>&1; then ok=$((ok+1)); else ok=0; fi
  sleep 5
done
chromium --app="http://127.0.0.1:3000/shell?overlay=1" --window-size=520,560 &
BROWSER=$!
WID=""
i=0
while [ $i -lt 90 ]; do
  WID=$(xdotool search --name '^ATANOR$' 2>/dev/null | head -1)
  [ -n "$WID" ] && break
  i=$((i+1)); sleep 1
done
if [ -n "$WID" ]; then
  xprop -id "$WID" -f _MOTIF_WM_HINTS 32c -set _MOTIF_WM_HINTS "2, 0, 0, 0, 0"
  wmctrl -i -r "$WID" -b add,above,sticky || true
fi
wait $BROWSER
