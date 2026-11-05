The throughput graphs for our busiest radios show absurd spikes: roughly once every few minutes a
single sample reads on the order of 10^18 bytes per second, and the next sample is back to normal.
Quieter radios never show it. `GET /v1/rates` on an affected AP returns the bad value while the
spike is on screen. The spikes line up with the moments the radio's byte counters roll over.

The AP agent's source is in `/app` (Go). Find the cause and fix it so the reported rates are
right. Existing behavior must keep working.
