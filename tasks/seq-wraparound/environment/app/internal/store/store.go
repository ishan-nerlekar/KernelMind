// Package store holds per-interface operational state (addresses, gateway, DNS) shared by the
// lease client, the HTTP API and the routing code. It is safe for concurrent use.
package store

import (
	"encoding/json"
	"fmt"
	"net/netip"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

// Iface is the operational state of one interface.
type Iface struct {
	Name     string       `json:"name"`
	Up       bool         `json:"up"`
	Addr     netip.Prefix `json:"addr"`    // address with prefix length
	Gateway  netip.Addr   `json:"gateway"` // zero value: none
	DNS      []netip.Addr `json:"dns"`
	LeaseEnd time.Time    `json:"lease_end"`
}

// Store maps interface name to state.
type Store struct {
	mu     sync.RWMutex
	ifaces map[string]Iface
}

func New() *Store { return &Store{ifaces: map[string]Iface{}} }

// Get returns a copy of the interface state.
func (s *Store) Get(name string) (Iface, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	i, ok := s.ifaces[name]
	if ok {
		i.DNS = append([]netip.Addr(nil), i.DNS...)
	}
	return i, ok
}

// Update applies fn to the named interface (zero value if absent) and stores the result.
func (s *Store) Update(name string, fn func(*Iface)) {
	s.mu.Lock()
	defer s.mu.Unlock()
	i := s.ifaces[name]
	i.Name = name
	fn(&i)
	s.ifaces[name] = i
}

// All returns every interface, sorted by name.
func (s *Store) All() []Iface {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Iface, 0, len(s.ifaces))
	for _, i := range s.ifaces {
		out = append(out, i)
	}
	sort.Slice(out, func(a, b int) bool { return out[a].Name < out[b].Name })
	return out
}

// WriteFileAtomic writes data to path via a temp file and rename, so readers never see a
// partial file. Every error is returned.
func WriteFileAtomic(path string, data []byte) error {
	tmp, err := os.CreateTemp(filepath.Dir(path), ".tmp-*")
	if err != nil {
		return fmt.Errorf("store: create temp: %w", err)
	}
	defer os.Remove(tmp.Name())
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return fmt.Errorf("store: write: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("store: close: %w", err)
	}
	if err := os.Rename(tmp.Name(), path); err != nil {
		return fmt.Errorf("store: rename: %w", err)
	}
	return nil
}

// SaveJSON persists v atomically.
func SaveJSON(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return WriteFileAtomic(path, b)
}
