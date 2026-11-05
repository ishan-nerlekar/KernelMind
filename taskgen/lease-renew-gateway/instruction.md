After the uplink router at one of our sites was replaced, every access point there kept sending
management traffic to the old gateway (10.20.0.1) and kept querying the old DNS resolver. The
problem cleared on each AP only after it was rebooted.

The DHCP server's log shows every AP renewing its lease on schedule, and each renewal reply
carries the new gateway (10.20.0.254) and the new resolver. On an affected AP, `GET /v1/interfaces`
still shows the old gateway, while its `lease_end` keeps moving forward with each renewal.

The AP agent's source is in `/app` (Go). Find the cause and fix it. Existing behavior must keep
working.
