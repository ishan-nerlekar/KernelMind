// Package dp simulates the radio datapath's per-peer state.
//
// The datapath tracks two kinds of peer. A link peer is a single-link station, keyed by its
// address on that link. A multi-link (MLO, Wi-Fi 7) station is tracked as one MLD peer, keyed by
// its MLD address, whose counters cover traffic on all of its links. The per-link addresses of
// an MLO station are not datapath peers.
package dp

import (
	"errors"
	"sync"
	"time"
)

type PeerType int

const (
	LinkPeer PeerType = iota
	MLDPeer
)

var ErrNoPeer = errors.New("dp: no such peer")

type key struct {
	addr string
	typ  PeerType
}

// Datapath is safe for concurrent use.
type Datapath struct {
	mu         sync.Mutex
	now        func() time.Time
	lastActive map[key]time.Time
}

// New returns an empty datapath. now is its clock.
func New(now func() time.Time) *Datapath {
	return &Datapath{now: now, lastActive: map[key]time.Time{}}
}

// AddPeer creates a peer, active as of now.
func (d *Datapath) AddPeer(addr string, typ PeerType) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.lastActive[key{addr, typ}] = d.now()
}

// RemovePeer deletes a peer, as firmware does when it kicks out a station that stopped
// responding. Removing a missing peer is a no-op.
func (d *Datapath) RemovePeer(addr string, typ PeerType) {
	d.mu.Lock()
	defer d.mu.Unlock()
	delete(d.lastActive, key{addr, typ})
}

// Traffic records that a peer sent or received data now.
func (d *Datapath) Traffic(addr string, typ PeerType) error {
	d.mu.Lock()
	defer d.mu.Unlock()
	k := key{addr, typ}
	if _, ok := d.lastActive[k]; !ok {
		return ErrNoPeer
	}
	d.lastActive[k] = d.now()
	return nil
}

// InactiveSec is the number of whole seconds since the peer last sent or received data.
func (d *Datapath) InactiveSec(addr string, typ PeerType) (int, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	t, ok := d.lastActive[key{addr, typ}]
	if !ok {
		return 0, ErrNoPeer
	}
	return int(d.now().Sub(t) / time.Second), nil
}
