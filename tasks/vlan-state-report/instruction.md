An access point reports dynamic VLAN assignment (DVA) as disabled on an SSID even though DVA is
enabled in that SSID's configuration. It happens when the VLANs are configured globally on the
access point rather than in the SSID's own VLAN list. SSIDs with their own VLAN list report correctly.

The state reporter is in `/app`. `CONTRACT.md` defines the expected behavior and `README.md` explains
how to run it. Fix the reporter so reported state matches the contract, without breaking validation or
dropping any other data. Keep `handle(request)` and the command-line interface working; standard
library only.
