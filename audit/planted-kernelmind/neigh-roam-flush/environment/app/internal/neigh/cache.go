// Package neigh is the agent's neighbor (ARP/NDP) cache: IP address to MAC per interface.
//
// The cache has a fixed capacity across all interfaces. When an interface goes down, its
// entries are no longer valid: the peers behind it may have moved or changed MAC.
package neigh

import (
	"errors"
	"fmt"
	"net/netip"
	"sort"
	"sync"
	"time"
)

var ErrFull = errors.New("neigh: cache full")

// Entry is one learned neighbor.
type Entry struct {
	IP      netip.Addr `json:"ip"`
	MAC     string     `json:"mac"`
	Iface   string     `json:"iface"`
	Learned time.Time  `json:"learned"`
}

// Cache is safe for concurrent use.
type Cache struct {
	mu       sync.Mutex
	capacity int
	entries  map[netip.Addr]Entry
	perIface map[string]int // entry count per interface
	total    int
}

func New(capacity int) *Cache {
	return &Cache{capacity: capacity, entries: map[netip.Addr]Entry{}, perIface: map[string]int{}}
}

// Learn adds or refreshes an entry. A new entry is refused with ErrFull at capacity.
func (c *Cache) Learn(e Entry) error {
	if !e.IP.IsValid() || e.MAC == "" || e.Iface == "" {
		return fmt.Errorf("neigh: bad entry %+v", e)
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, ok := c.entries[e.IP]; ok {
		c.entries[e.IP] = e
		return nil
	}
	if c.total >= c.capacity {
		return fmt.Errorf("%w (%d entries)", ErrFull, c.total)
	}
	c.entries[e.IP] = e
	c.perIface[e.Iface]++
	c.total++
	return nil
}

// Lookup returns the entry for ip.
func (c *Cache) Lookup(ip netip.Addr) (Entry, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	e, ok := c.entries[ip]
	return e, ok
}

// Flush removes every entry learned on iface.
func (c *Cache) Flush(iface string) int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.flushLocked(iface)
}

func (c *Cache) flushLocked(iface string) int {
	n := 0
	for ip, e := range c.entries {
		if e.Iface == iface {
			delete(c.entries, ip)
			n++
		}
	}
	c.total -= c.perIface[iface]
	delete(c.perIface, iface)
	return n
}

// LinkDown is called when an interface loses carrier. Its neighbors are forgotten.
func (c *Cache) LinkDown(iface string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.flushLocked(iface)
}

// Len is the number of entries.
func (c *Cache) Len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.total
}

// Capacity is the configured maximum.
func (c *Cache) Capacity() int { return c.capacity }

// Entries returns all entries sorted by interface then IP.
func (c *Cache) Entries() []Entry {
	c.mu.Lock()
	defer c.mu.Unlock()
	out := make([]Entry, 0, len(c.entries))
	for _, e := range c.entries {
		out = append(out, e)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Iface != out[j].Iface {
			return out[i].Iface < out[j].Iface
		}
		return out[i].IP.Less(out[j].IP)
	})
	return out
}
