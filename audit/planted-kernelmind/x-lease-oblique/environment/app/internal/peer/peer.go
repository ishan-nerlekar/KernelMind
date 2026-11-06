// Package peer tracks mesh peers seen by the AP.
//
// Each poll of a peer ends in one of three results. OK refreshes the peer. NotFound means the
// peer table no longer lists it; after MissLimit consecutive NotFound results the peer is
// removed. Timeout means the statistics request did not complete: it says nothing about
// whether the peer is still there, so presence is unchanged and the peer is only marked stale.
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
	case NotFound:
		if !ok {
			return
		}
		p.Misses++
		p.Stale = false
		if p.Misses >= t.missLimit {
			delete(t.peers, name)
		}
	case Timeout:
		if ok {
			p.Stale = true
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
