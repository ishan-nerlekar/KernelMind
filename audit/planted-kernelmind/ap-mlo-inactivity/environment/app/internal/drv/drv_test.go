package drv

import (
	"testing"
	"time"

	"apnet/internal/dp"
)

func TestInactiveSecSingleLink(t *testing.T) {
	now := time.Date(2026, 10, 23, 9, 0, 0, 0, time.UTC)
	d := dp.New(func() time.Time { return now })
	v := New(d)
	v.AddStation("02:00:00:00:00:01", "")
	now = now.Add(42 * time.Second)
	if s, err := v.InactiveSec("02:00:00:00:00:01"); err != nil || s != 42 {
		t.Fatalf("got %d, %v", s, err)
	}
	v.RemoveStation("02:00:00:00:00:01")
	if _, err := v.InactiveSec("02:00:00:00:00:01"); err == nil {
		t.Fatal("removed station still reported")
	}
}
