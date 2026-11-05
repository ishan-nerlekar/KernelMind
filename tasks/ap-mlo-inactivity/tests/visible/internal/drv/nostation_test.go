package drv

import (
	"testing"
	"time"

	"apnet/internal/dp"
)

func TestUnknownStationIsNoStation(t *testing.T) {
	v := New(dp.New(time.Now))
	if _, err := v.InactiveSec("02:00:00:00:00:09"); err != ErrNoStation {
		t.Fatalf("got %v, want ErrNoStation", err)
	}
}
