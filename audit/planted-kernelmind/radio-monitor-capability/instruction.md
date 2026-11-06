We pushed a configuration that put radio `r0` on access point ap1 into monitor mode for a site
survey. The controller reported the push as applied and `GET /v1/radios` on ap1 shows `r0` in
`monitor` mode, but `r0`'s hardware has no monitor support: the radio stopped serving clients
entirely until we pushed it back to `ap` mode. Asking the same radio for `mesh` mode, which it
also doesn't support, is correctly refused.

The AP agent's source is in `/app` (Go). Find the cause and fix it. Existing behavior must keep
working.
