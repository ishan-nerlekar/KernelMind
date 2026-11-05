package drv

import (
	"testing"
	"time"

	"apnet/internal/dp"
)

func TestInactiveSecMLO(t *testing.T) {
	now := time.Date(2026, 10, 23, 9, 0, 0, 0, time.UTC)
	d := dp.New(func() time.Time { return now })
	v := New(d)
	v.AddStation("02:00:00:00:00:51", "fc:b2:14:c1:e5:4a")
	now = now.Add(300 * time.Second)
	d.Traffic("fc:b2:14:c1:e5:4a", dp.MLDPeer)
	now = now.Add(7 * time.Second)
	if s, err := v.InactiveSec("02:00:00:00:00:51"); err != nil || s != 7 {
		t.Fatalf("got %d, %v; want 7 s idle", s, err)
	}
}
