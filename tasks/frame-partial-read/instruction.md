Since we started pushing the full production configuration (a few hundred SSIDs) to remote sites,
config pushes fail intermittently. The controller reports errors like
`controller: push to ap7 failed after 4 attempts: EOF`, sometimes `i/o timeout`. On the agent
side the log shows lines like `decode: wire: truncated record` around the same time.

Small configurations always push fine, and pushes to APs in the same building as the controller
almost always succeed. The failures are much more frequent to sites behind slow or long WAN links.

The source for the agent and controller is in `/app` (Go). Find the cause and fix it. Existing
behavior must keep working.
