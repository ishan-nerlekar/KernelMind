package stats

import (
	"testing"
	"time"
)

func TestRateAcrossWrap(t *testing.T) {
	prev := Sample{At: t0, RxBytes: 0xFFFFFF00, TxBytes: 0xFFFFFFFF}
	cur := Sample{At: t0.Add(2 * time.Second), RxBytes: 0x00000100, TxBytes: 0x00000003}
	r, err := Between(prev, cur)
	if err != nil {
		t.Fatal(err)
	}
	if r.RxBps != 256 || r.TxBps != 2 {
		t.Fatalf("rate across wrap = %+v, want rx 256 B/s tx 2 B/s", r)
	}
}

func TestTrackerAcrossWrap(t *testing.T) {
	tr := NewTracker()
	_ = tr.Observe("wlan0", Sample{At: t0, RxBytes: 4294967000})
	_ = tr.Observe("wlan0", Sample{At: t0.Add(time.Second), RxBytes: 704})
	if r := tr.Rates()["wlan0"]; r.RxBps != 1000 {
		t.Fatalf("rate %+v, want 1000 B/s", r)
	}
}

func TestRateNoWrapUnchanged(t *testing.T) {
	r, _ := Between(Sample{At: t0, RxBytes: 10, TxBytes: 4000000000}, Sample{At: t0.Add(time.Second), RxBytes: 20, TxBytes: 4000000500})
	if r.RxBps != 10 || r.TxBps != 500 {
		t.Fatalf("rate %+v", r)
	}
}
