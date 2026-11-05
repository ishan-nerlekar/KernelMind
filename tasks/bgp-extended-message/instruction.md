At 14:00 yesterday we rolled out a routine change on our edge router edge1 (see
`/app/debug/change.txt`). Within a minute, the BGP sessions from edge1 to our two older aggregation
routers, rtr7 and rtr8, started flapping: they come up, drop within a second or two, come up
again, and so on. Every other session on edge1, including the other routers that receive exactly
the same routes, stayed up the whole time. Rolling the change back stops the flapping.

The older routers' vendor says their routers are behaving correctly and pointed us at their log
(`/app/debug/rtr7-bgpd.log`). Other material we collected is in `/app/debug/` too.

edge1 runs GoBGP with our in-house changes; the source is in `/app`. Find the cause on our side and
fix it. Existing behavior must keep working.
