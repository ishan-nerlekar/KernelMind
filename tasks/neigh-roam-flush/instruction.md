At sites where clients move between the AP's `lan0` and `lan1` bridges during the day, the
neighbor cache goes wrong after an interface is flushed. `GET /v1/neighbors` reports a `count`
that doesn't match the number of `entries` it lists. Some APs then refuse new neighbors with
"neigh: cache full" while holding only a handful of entries; others end up holding more entries
than the configured capacity.

APs where clients never move between interfaces don't show the problem.

The AP agent's source is in `/app` (Go). Find the cause and fix it. Existing behavior must keep
working.
