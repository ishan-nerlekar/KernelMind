On our busiest access points, mesh peers keep disappearing from `GET /v1/peers` and then
reappearing a minute or so later. The mesh topology view flaps constantly at those sites, and
alerts fire for "peer lost".

The wireless links to those peers stay up the whole time and traffic keeps flowing. The agent log
shows the per-peer statistics requests timing out when the AP is under load. Peers that really
leave must still be removed after the usual number of missed polls.

The AP agent's source is in `/app` (Go). Find the cause and fix it. Existing behavior must keep
working.
