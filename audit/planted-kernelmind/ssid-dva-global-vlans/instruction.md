Our monitoring shows dynamic VLAN assignment (DVA) as disabled on SSIDs at several sites, even
though DVA is enabled in their configuration and clients on those SSIDs do get placed in the right
VLANs. On an affected AP, `GET /v1/ssids` reports `"dva": false` for those SSIDs.

The affected sites define their VLANs once for the whole access point rather than listing them on
each SSID. SSIDs that list their own VLANs report DVA correctly.

The AP agent's source is in `/app` (Go). Find the cause and fix it so the reported state is
correct. Existing behavior must keep working.
