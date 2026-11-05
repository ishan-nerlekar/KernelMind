One of our lab access points, which receives a configuration push every few seconds from an
automated test rig, stopped accepting configuration after running for several days. Every push to
it now fails: the controller logs "stale sequence" retries followed by
`push to ap1 failed after 4 attempts`. Restarting the agent fixes it, and it has happened again
since, again after several days. Other APs that receive far fewer pushes have never shown it.

The source for the agent and controller is in `/app` (Go). Find the cause and fix it. Existing
behavior must keep working.
