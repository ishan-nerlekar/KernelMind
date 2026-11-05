Every night around 02:00, our RPKI validator restarts for its automatic upgrade check. During the
five or so minutes it takes to come back, our edge router misbehaves: routes we normally drop as
RPKI-invalid (we've seen two known hijack attempts get through) are accepted, and our customers'
routes lose their "valid" state, which our downstream policy depends on. At around 02:03 everything
returns to normal on its own.

The validator's vendor says the validator is behaving correctly while it restarts. The router is
supposed to keep using its last known validation data until the validator is back, and it does
exactly that when the validator is simply unreachable (we tested by blocking the port).

Logs and samples from last night's window are in `/app/debug/`. The BGP daemon's source is in
`/app` (it's GoBGP with our in-house changes). Find the cause and fix it. Existing behavior must
keep working.
