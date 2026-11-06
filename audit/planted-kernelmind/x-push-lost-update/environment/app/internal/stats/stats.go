// Package stats turns raw interface counters into rates.
//
// Radio hardware exposes 32-bit byte and packet counters that wrap to zero after 2^32-1.
// Between two samples a counter can wrap at most once at realistic sample intervals, so the
// delta is computed modulo 2^32.
package stats

import (
	"errors"
	"sync"
	"time"
)

// Sample is one reading of an interface's counters.
type Sample struct {
	At      time.Time `json:"at"`
	RxBytes uint32    `json:"rx_bytes"`
	TxBytes uint32    `json:"tx_bytes"`
}

// Rate is throughput between two samples.
type Rate struct {
	RxBps float64 `json:"rx_bps"` // bytes per second
	TxBps float64 `json:"tx_bps"`
}

var ErrInterval = errors.New("stats: samples not in time order")

// delta is the counter increase from a to b, allowing one wrap.
func delta(a, b uint32) uint64 { return uint64(b - a) }

// Between computes the rate from prev to cur.
func Between(prev, cur Sample) (Rate, error) {
	secs := cur.At.Sub(prev.At).Seconds()
	if secs <= 0 {
		return Rate{}, ErrInterval
	}
	return Rate{
		RxBps: float64(delta(prev.RxBytes, cur.RxBytes)) / secs,
		TxBps: float64(delta(prev.TxBytes, cur.TxBytes)) / secs,
	}, nil
}

// Tracker keeps the last sample and rate per interface. Safe for concurrent use.
type Tracker struct {
	mu    sync.Mutex
	last  map[string]Sample
	rates map[string]Rate
}

func NewTracker() *Tracker {
	return &Tracker{last: map[string]Sample{}, rates: map[string]Rate{}}
}

// Observe records a sample and updates the interface's rate.
func (t *Tracker) Observe(iface string, s Sample) error {
	t.mu.Lock()
	defer t.mu.Unlock()
	if prev, ok := t.last[iface]; ok {
		r, err := Between(prev, s)
		if err != nil {
			return err
		}
		t.rates[iface] = r
	}
	t.last[iface] = s
	return nil
}

// Rates returns a copy of the current rates.
func (t *Tracker) Rates() map[string]Rate {
	t.mu.Lock()
	defer t.mu.Unlock()
	out := make(map[string]Rate, len(t.rates))
	for k, v := range t.rates {
		out[k] = v
	}
	return out
}
