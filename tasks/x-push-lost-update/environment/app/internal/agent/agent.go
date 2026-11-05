// Package agent is the AP agent: it applies configuration pushed by the controller, drives the
// radios, and reports operational state over HTTP.
//
// Applying a push is all-or-nothing. Either every radio is programmed, the configuration is
// persisted and the push is acknowledged as applied, or the hardware is left exactly as it was
// and the push is rejected.
package agent

import (
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"sort"
	"sync"

	"apnet/internal/config"
	"apnet/internal/frame"
	"apnet/internal/msg"
	"apnet/internal/neigh"
	"apnet/internal/peer"
	"apnet/internal/radio"
	"apnet/internal/seqnum"
	"apnet/internal/state"
	"apnet/internal/stats"
	"apnet/internal/store"
)

// Options configure a new agent.
type Options struct {
	Name          string
	Radios        []*radio.Radio
	Hardware      radio.Hardware
	StatePath     string // where the applied configuration is persisted
	NeighCapacity int
	PeerMissLimit int
	Logger        *log.Logger
}

// Agent is safe for concurrent use.
type Agent struct {
	name      string
	hw        radio.Hardware
	statePath string
	log       *log.Logger

	mu      sync.Mutex
	cfg     *config.Config
	lastSeq uint16
	haveSeq bool
	applied map[string]bool // push IDs already applied
	radios  map[string]*radio.Radio

	Store *store.Store
	Neigh *neigh.Cache
	Peers *peer.Tracker
	Stats *stats.Tracker
}

func New(o Options) *Agent {
	if o.NeighCapacity == 0 {
		o.NeighCapacity = 1024
	}
	if o.PeerMissLimit == 0 {
		o.PeerMissLimit = 3
	}
	if o.Logger == nil {
		o.Logger = log.New(io.Discard, "", 0)
	}
	a := &Agent{
		name:      o.Name,
		hw:        o.Hardware,
		statePath: o.StatePath,
		log:       o.Logger,
		cfg:       &config.Config{},
		applied:   map[string]bool{},
		radios:    map[string]*radio.Radio{},
		Store:     store.New(),
		Neigh:     neigh.New(o.NeighCapacity),
		Peers:     peer.NewTracker(o.PeerMissLimit),
		Stats:     stats.NewTracker(),
	}
	for _, r := range o.Radios {
		a.radios[r.Name] = r
	}
	return a
}

func (a *Agent) Name() string { return a.name }

// Config returns a copy of the applied configuration and its sequence number.
func (a *Agent) Config() (*config.Config, uint16) {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.cfg.Clone(), a.lastSeq
}

// Radios returns a snapshot of radio state sorted by name.
func (a *Agent) Radios() []radio.Radio {
	a.mu.Lock()
	defer a.mu.Unlock()
	out := make([]radio.Radio, 0, len(a.radios))
	for _, r := range a.radios {
		cp := *r
		cp.Caps = map[radio.Capability]bool{}
		for k, v := range r.Caps {
			cp.Caps[k] = v
		}
		out = append(out, cp)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

// SSIDState derives the operational SSID state from the applied configuration.
func (a *Agent) SSIDState() ([]state.SSID, error) {
	a.mu.Lock()
	cfg := a.cfg.Clone()
	a.mu.Unlock()
	return state.Derive(cfg)
}

func reject(p msg.Push, err error) msg.Ack {
	return msg.Ack{Seq: p.Seq, PushID: p.PushID, Status: msg.StatusRejected, Error: err.Error()}
}

// ApplyPush applies one configuration push and returns the acknowledgement to send.
func (a *Agent) ApplyPush(p msg.Push) msg.Ack {
	a.mu.Lock()
	defer a.mu.Unlock()

	// A retransmission of a push we already applied is acknowledged without reapplying.
	if a.applied[p.PushID] {
		return msg.Ack{Seq: p.Seq, PushID: p.PushID, Status: msg.StatusDuplicate}
	}
	if a.haveSeq && !seqnum.Newer(p.Seq, a.lastSeq) {
		return msg.Ack{Seq: p.Seq, PushID: p.PushID, Status: msg.StatusStale}
	}
	cfg, err := config.Parse(p.Body)
	if err != nil {
		return reject(p, err)
	}

	// Check every radio before touching hardware.
	for _, rc := range cfg.Radios {
		r, ok := a.radios[rc.Name]
		if !ok {
			return reject(p, fmt.Errorf("unknown radio %q", rc.Name))
		}
		if err := r.Check(rc); err != nil {
			return reject(p, err)
		}
	}

	// Program radios, remembering how to undo each step.
	var undo []config.Radio
	rollback := func() {
		for i := len(undo) - 1; i >= 0; i-- {
			prev := undo[i]
			if err := a.radios[prev.Name].Apply(a.hw, prev); err != nil {
				a.log.Printf("rollback radio %s: %v", prev.Name, err)
			}
		}
	}
	for _, rc := range cfg.Radios {
		r := a.radios[rc.Name]
		prev := config.Radio{Name: r.Name, Mode: r.Mode, Channel: r.Channel}
		if err := r.Apply(a.hw, rc); err != nil {
			undo = append(undo, prev) // Apply may have changed the mode before failing
			rollback()
			return reject(p, err)
		}
		undo = append(undo, prev)
	}

	if a.statePath != "" {
		// Writing flash can take tens of milliseconds; don't hold up state readers meanwhile.
		a.mu.Unlock()
		err := store.SaveJSON(a.statePath, cfg)
		a.mu.Lock()
		if err != nil {
			rollback()
			return reject(p, fmt.Errorf("persist config: %w", err))
		}
	}

	a.cfg, a.lastSeq, a.haveSeq = cfg, p.Seq, true
	a.applied[p.PushID] = true
	a.log.Printf("applied push %s seq %d revision %d", p.PushID, p.Seq, cfg.Revision)
	return msg.Ack{Seq: p.Seq, PushID: p.PushID, Status: msg.StatusApplied}
}

// ServeControl accepts controller connections until ln is closed. Each connection carries a
// stream of framed pushes; each push gets one framed ack.
func (a *Agent) ServeControl(ln net.Listener) error {
	for {
		conn, err := ln.Accept()
		if err != nil {
			if errors.Is(err, net.ErrClosed) {
				return nil
			}
			return err
		}
		go a.handleConn(conn)
	}
}

func (a *Agent) handleConn(conn net.Conn) {
	defer conn.Close()
	for {
		b, err := frame.Read(conn)
		if err != nil {
			if !errors.Is(err, io.EOF) {
				a.log.Printf("control %s: read: %v", conn.RemoteAddr(), err)
			}
			return
		}
		p, err := msg.DecodePush(b)
		if err != nil {
			a.log.Printf("control %s: decode: %v", conn.RemoteAddr(), err)
			return
		}
		ack, err := a.ApplyPush(p).Encode()
		if err != nil {
			a.log.Printf("control %s: encode ack: %v", conn.RemoteAddr(), err)
			return
		}
		if err := frame.Write(conn, ack); err != nil {
			a.log.Printf("control %s: write: %v", conn.RemoteAddr(), err)
			return
		}
	}
}
