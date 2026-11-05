// Package station keeps the AP's associated client stations and disconnects idle ones.
//
// A station is first checked MaxInactivity after it associates, and after that whenever it could
// have been idle for MaxInactivity. A station idle that long is disassociated with reason 4
// (inactivity), as in IEEE 802.11.
package station

import (
	"errors"
	"sort"
	"sync"
	"time"

	"apnet/internal/drv"
)

// Reason is an IEEE 802.11 reason code.
type Reason int

const (
	ReasonLeaving    Reason = 3 // station is leaving
	ReasonInactivity Reason = 4 // disassociated due to inactivity
)

var ErrAssociated = errors.New("station: already associated")

// Driver is the part of the radio driver the manager uses.
type Driver interface {
	AddStation(addr, mld string)
	RemoveStation(addr string)
	InactiveSec(addr string) (int, error)
}

// Station is one associated client.
type Station struct {
	Addr  string    `json:"addr"`          // address the client associated with on this AP
	MLD   string    `json:"mld,omitempty"` // MLD address of a multi-link (MLO) client
	Since time.Time `json:"since"`
	next  time.Time // next inactivity check
}

// Event records a disassociation.
type Event struct {
	At     time.Time `json:"at"`
	Addr   string    `json:"addr"`
	Reason Reason    `json:"reason"`
}

// Manager is safe for concurrent use.
type Manager struct {
	mu            sync.Mutex
	drv           Driver
	maxInactivity time.Duration
	stations      map[string]*Station
	events        []Event
}

func NewManager(d Driver, maxInactivity time.Duration) *Manager {
	return &Manager{drv: d, maxInactivity: maxInactivity, stations: map[string]*Station{}}
}

// Associate admits a client. mld is "" for a single-link association.
func (m *Manager) Associate(addr, mld string, now time.Time) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.stations[addr]; ok {
		return ErrAssociated
	}
	m.drv.AddStation(addr, mld)
	m.stations[addr] = &Station{Addr: addr, MLD: mld, Since: now, next: now.Add(m.maxInactivity)}
	return nil
}

// Disassociate removes a station at the client's request or the AP's.
func (m *Manager) Disassociate(addr string, r Reason, now time.Time) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if st, ok := m.stations[addr]; ok {
		m.remove(st, r, now)
	}
}

func (m *Manager) remove(st *Station, r Reason, now time.Time) {
	delete(m.stations, st.Addr)
	m.drv.RemoveStation(st.Addr)
	m.events = append(m.events, Event{At: now, Addr: st.Addr, Reason: r})
}

// Check runs the inactivity check for every station that is due. Call it periodically.
func (m *Manager) Check(now time.Time) {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, st := range m.sorted() {
		if now.Before(st.next) {
			continue
		}
		secs, err := m.drv.InactiveSec(st.Addr)
		idle := time.Duration(secs) * time.Second
		switch {
		case errors.Is(err, drv.ErrNoStation):
			// The driver no longer has this station: the client left without disassociating
			// (powered off, out of range). Drop the entry so the client can associate again.
			m.remove(st, ReasonInactivity, now)
		case err != nil:
			// The counters couldn't be read; try again next interval.
			st.next = now.Add(m.maxInactivity)
		case idle >= m.maxInactivity:
			m.remove(st, ReasonInactivity, now)
		default:
			st.next = now.Add(m.maxInactivity - idle)
		}
	}
}

func (m *Manager) sorted() []*Station {
	out := make([]*Station, 0, len(m.stations))
	for _, st := range m.stations {
		out = append(out, st)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Addr < out[j].Addr })
	return out
}

// Stations lists associated stations sorted by address.
func (m *Manager) Stations() []Station {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := []Station{}
	for _, st := range m.sorted() {
		out = append(out, *st)
	}
	return out
}

// Events returns the disassociation log.
func (m *Manager) Events() []Event {
	m.mu.Lock()
	defer m.mu.Unlock()
	return append([]Event(nil), m.events...)
}
