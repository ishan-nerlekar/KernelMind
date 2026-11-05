We buy transit from the same provider (AS 64500) at two sites, Amsterdam and Frankfurt, with one
BGP session at each. For a customer network of theirs, 203.0.113.0/24 (origin AS 64510), the
provider's routes differ only in that the Frankfurt route has a longer AS path (it passes through
two more of their partner networks) and a lower MED.

Our router sends the traffic out through Frankfurt. Our network team expected Amsterdam, and the
other router vendor we're migrating from also chose Amsterdam for the same routes. Latency to that
customer has roughly doubled. Local preference is the same on both sessions.

The BGP daemon's source is in `/app`: it's GoBGP. Find the cause and fix it. Existing behavior must
keep working.
