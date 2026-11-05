Collected during incident INC-2304 (2026-11-04). Our side is edge1 (AS 4200000100, 10.20.0.1).

change.txt          the change that was being rolled out
edge1-gobgpd.toml   edge1's BGP configuration (excerpt: global and aggregation neighbors)
edge1-neighbors.txt `gobgp neighbor <addr>` on edge1 for rtr7 and rtr11
edge1-adj-out.txt   advertised route counts on edge1
rtr7-show.txt       route counts on rtr7

edge1's gobgpd log has nothing for the incident window (production log level is "error").
