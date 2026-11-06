Last Tuesday the network team replaced the router at our Pune office. Since then the access points
there have one by one stopped reaching our central syslog collector and our time servers: we no
longer receive their logs, and their clocks are starting to drift. Everything else about them looks
healthy. They keep serving Wi-Fi clients, the controller can still push configuration to them, and
they answer on their management API.

Any AP we reboot comes back fine and stays fine. The new router uses a different address from the
old one, and the site's name server moved to a new address at the same time; the APs themselves
kept their own addresses.

The AP software is in `/app` (Go). Find the cause and fix it. Existing behavior must keep working.
