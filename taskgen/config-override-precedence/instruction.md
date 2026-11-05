Our guest SSID has client isolation explicitly switched off in its own settings so guests can reach
the lobby printer, but they can't: `GET /v1/ssids` shows `"isolation": true` for it. The access
point's site-wide defaults have isolation switched on, which is what we want for every other SSID.

We see the same pattern with other settings: a value set on one SSID is ignored whenever the site
also sets a default for it. SSID settings that have no site default work fine.

The AP agent's source is in `/app` (Go). Find the cause and fix it. Existing behavior must keep
working.
