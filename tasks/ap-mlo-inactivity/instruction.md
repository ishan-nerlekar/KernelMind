Last week we upgraded our access points from software 23.0 to 23.1. Since then, Wi-Fi 7 laptops
that connect using multi-link operation (MLO) are disconnected every 15 minutes, even in the middle
of a video call. The AP reports the reason as inactivity. Clients that connect on a single link are
not affected, and 23.0 didn't do this.

The AP software is in `/app`, with its git history (releases are tagged `23.0` and `23.1`). What we
collected during the incident is in `/app/debug/`.

Find the cause and fix it. Existing behavior must keep working.
