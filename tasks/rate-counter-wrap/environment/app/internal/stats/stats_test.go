package stats

import (
	"errors"
	"testing"
	"time"
)

var t0 = time.Date(2026, 11, 1, 0, 0, 0, 0, time.UTC)

func TestBetween(t *testing.T) {
	r, err := Between(Sample{At: t0, RxBytes: 1000, TxBytes: 0}, Sample{At: t0.Add(2 * time.Second), RxBytes: 5000, TxBytes: 600})
	if err != nil {
		t.Fatal(err)
	}
	if r.RxBps != 2000 || r.TxBps != 300 {
		t.Fatalf("rate %+v", r)
	}
}

func TestBetweenOrder(t *testing.T) {
	if _, err := Between(Sample{At: t0}, Sample{At: t0}); !errors.Is(err, ErrInterval) {
		t.Fatalf("same time: %v", err)
	}
	if _, err := Between(Sample{At: t0.Add(time.Second)}, Sample{At: t0}); !errors.Is(err, ErrInterval) {
		t.Fatalf("backwards: %v", err)
	}
}

func TestTracker(t *testing.T) {
	tr := NewTracker()
	_ = tr.Observe("wlan0", Sample{At: t0, RxBytes: 100})
	if len(tr.Rates()) != 0 {
		t.Fatal("rate after a single sample")
	}
	_ = tr.Observe("wlan0", Sample{At: t0.Add(time.Second), RxBytes: 1100, TxBytes: 50})
	r := tr.Rates()["wlan0"]
	if r.RxBps != 1000 || r.TxBps != 50 {
		t.Fatalf("rate %+v", r)
	}
}
