// Package peer tracks mesh peers seen by the AP.
//
// Each poll of a peer ends in one of three results: OK, NotFound or Timeout. A peer that misses
// MissLimit consecutive polls is removed.
package peer

import (
	"sort"
	"sync"
	"time"
)

type Result int

const (
	OK Result = iota
	NotFound
	Timeout
)

// Peer is the tracked state of one peer.
type Peer struct {
	Name     string    `json:"name"`
	LastSeen time.Time `json:"last_seen"`
	Misses   int       `json:"misses"` // consecutive NotFound results
	Stale    bool      `json:"stale"`  // last poll timed out
}

// Tracker is safe for concurrent use.
type Tracker struct {
	mu        sync.Mutex
	missLimit int
	peers     map[string]*Peer
}

func NewTracker(missLimit int) *Tracker {
	if missLimit < 1 {
		missLimit = 1
	}
	return &Tracker{missLimit: missLimit, peers: map[string]*Peer{}}
}

// Observe records one poll result.
func (t *Tracker) Observe(name string, r Result, now time.Time) {
	t.mu.Lock()
	defer t.mu.Unlock()
	p, ok := t.peers[name]
	switch r {
	case OK:
		if !ok {
			p = &Peer{Name: name}
			t.peers[name] = p
		}
		p.LastSeen, p.Misses, p.Stale = now, 0, false
	case NotFound, Timeout:
		if !ok {
			return
		}
		p.Misses++
		p.Stale = r == Timeout
		if p.Misses >= t.missLimit {
			delete(t.peers, name)
		}
	}
}

// Present lists current peers sorted by name.
func (t *Tracker) Present() []Peer {
	t.mu.Lock()
	defer t.mu.Unlock()
	out := make([]Peer, 0, len(t.peers))
	for _, p := range t.peers {
		out = append(out, *p)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}
