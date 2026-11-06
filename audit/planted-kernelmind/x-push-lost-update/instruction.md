We run two controller instances behind a load balancer. Both keep control connections open to every
access point and take push sequence numbers from a shared counter, so an AP may receive pushes from
either one.

During bulk changes (for example, re-planning channels across a building, when many pushes go out
within a second or two), some APs end up out of sync: the controller recorded its newest push as
applied, but `GET /v1/config` on the AP shows an older revision. On some of those APs,
`GET /v1/radios` doesn't even match the AP's own `/v1/config`. Sending one more push fixes the AP.
We have never seen it outside bulk changes.

The source for the agent and controller is in `/app` (Go). Find the cause and fix it. Existing
behavior must keep working.
