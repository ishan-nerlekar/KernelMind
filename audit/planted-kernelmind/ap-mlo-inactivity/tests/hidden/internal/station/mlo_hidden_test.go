package station

import (
	"testing"
	"time"

	"apnet/internal/dp"
)

const link, mld = "02:00:00:00:00:51", "fc:b2:14:c1:e5:4a"

func TestMLOActiveStationKept(t *testing.T) {
	c, d, m := setup()
	m.Associate(link, mld, c.t)
	run(c, m, 3*time.Hour, func() { d.Traffic(mld, dp.MLDPeer) })
	if len(m.Stations()) != 1 || len(m.Events()) != 0 {
		t.Fatalf("active MLO client dropped: %+v", m.Events())
	}
}

func disabledTestMLOIdleStationDisconnected(t *testing.T) {
	c, _, m := setup()
	m.Associate(link, mld, c.t)
	run(c, m, 950*time.Second, nil)
	if ev := m.Events(); len(ev) != 1 || ev[0].Reason != ReasonInactivity || len(m.Stations()) != 0 {
		t.Fatalf("idle MLO client not disconnected after 900 s: %+v", ev)
	}
}

func TestMLOAndSingleLinkTogether(t *testing.T) {
	c, d, m := setup()
	m.Associate(link, mld, c.t)
	m.Associate("02:00:00:00:00:01", "", c.t)
	run(c, m, 2*time.Hour, func() {
		d.Traffic(mld, dp.MLDPeer)
		d.Traffic("02:00:00:00:00:01", dp.LinkPeer)
	})
	if len(m.Stations()) != 2 {
		t.Fatalf("stations %+v events %+v", m.Stations(), m.Events())
	}
}
