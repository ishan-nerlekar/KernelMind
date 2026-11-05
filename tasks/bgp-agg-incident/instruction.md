At 14:00 yesterday we started redistributing about 2,100 data-center host routes into BGP on our
edge router edge1. At 14:30 the aggregation router rtr7 (an older platform) was rebooted for planned
maintenance, and since it came back it hasn't had those routes: its session with edge1 won't stay
up. The newer aggregation router rtr11, configured the same way on edge1, is fine.

We couldn't collect useful logs from production, but `/app/debug/repro.sh` reproduces the setup in
this container: it builds edge1's gobgpd from `/app` and connects it to stand-ins for the data-center
source, rtr7 and rtr11 (see `/app/debug/README.txt`).

edge1 runs GoBGP with our in-house changes; the source is in `/app`. Find the cause on our side and
fix it, so that rtr7's session stays up and it receives every route. Existing behavior must keep
working.
