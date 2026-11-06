package station

import (
	"testing"
	"time"

	"apnet/internal/dp"
)

// A client that disappears without disassociating (firmware has kicked out its peer) must not
// keep its station entry, or its next association is refused as a duplicate.
func disabledTestVanishedStationCanRejoin(t *testing.T) {
	for _, mld := range []string{"", "fc:b2:14:c1:e5:4a"} {
		c, d, m := setup()
		m.Associate("02:00:00:00:00:01", mld, c.t)
		if mld == "" {
			d.RemovePeer("02:00:00:00:00:01", dp.LinkPeer)
		} else {
			d.RemovePeer(mld, dp.MLDPeer)
		}
		run(c, m, 950*time.Second, nil)
		if len(m.Stations()) != 0 {
			t.Fatalf("mld=%q: vanished station still listed after the inactivity check", mld)
		}
		if err := m.Associate("02:00:00:00:00:01", mld, c.t); err != nil {
			t.Fatalf("mld=%q: rejoin refused: %v", mld, err)
		}
	}
}
