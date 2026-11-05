Last night our transit provider (AS 64500) moved our traffic to a new edge router on their side.
The BGP session to them stayed up the whole time; they simply started advertising every prefix
with a new next hop, 192.0.2.254 instead of 192.0.2.1. Since then, for many prefixes our RIB shows
two paths from that same neighbor, one with each next hop, and for some of them the path via the old
next hop is still selected as best, so that traffic is blackholed. When the provider withdraws one
of those prefixes it doesn't always leave our RIB either. Resetting the BGP session clears
everything up until the next change.

Possibly related: at the internet exchange, two route servers sometimes advertise the same prefix
with the same third-party next hop, and we only ever see one of the two paths in our RIB.

The BGP daemon's source is in `/app`: it's GoBGP. Find the cause and fix it. Existing behavior must
keep working.
