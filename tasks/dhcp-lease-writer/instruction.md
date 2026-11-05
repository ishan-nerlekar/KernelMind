After a DHCP lease update, some interfaces come back with the wrong addressing mode. On a freshly
created configuration everything looks right, but when an existing configuration is updated the
`BOOTPROTO` line is sometimes missing, sometimes still says `static`, and sometimes appears more than
once. The other lease fields (address, netmask, lease time) are refreshed correctly.

The configuration writer is in `/app`. `CONTRACT.md` describes the exact expected behavior and
`README.md` explains how to run it. Fix the writer so every lease update satisfies the contract.
Keep the command-line interface unchanged and use only the Python standard library.
