At 14:00 yesterday we redistributed about 2,100 data-center host routes into BGP on our edge router
edge1 (see `/app/debug/change.txt`). Our two older aggregation routers, rtr7 and rtr8, only ever
received a fraction of them. Every other peer got all of them, including the two newer aggregation
routers, rtr11 and rtr12, which have the same configuration on edge1 as rtr7 and rtr8. No session
went down, and edge1 lists all of the routes as advertised to rtr7 and rtr8.

The older routers' vendor says their side is fine. What we collected is in `/app/debug/`.

edge1 runs GoBGP with our in-house changes; the source is in `/app`. Find the cause on our side and
fix it. Existing behavior must keep working.
