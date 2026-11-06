// Package lease is a DHCP-style address lease client for the AP's uplink interfaces.
//
// The client acquires a lease, publishes it to the interface store, and renews it at T1
// (half the lease duration, as in RFC 2131).
package lease

import (
	"context"
	"errors"
	"fmt"
	"net/netip"
	"sync"
	"time"

	"apnet/internal/store"
)

// Offer is what the server grants.
type Offer struct {
	Addr    netip.Prefix
	Gateway netip.Addr
	DNS     []netip.Addr
	Seconds uint32 // lease duration in seconds
}

// Server is the lease server (a DHCP server in production; FakeServer in simulation and tests).
type Server interface {
	Discover(iface string) (Offer, error)
	Renew(iface string, addr netip.Addr) (Offer, error)
}

// Clock abstracts time for tests.
type Clock interface{ Now() time.Time }

type realClock struct{}

func (realClock) Now() time.Time { return time.Now() }

var ErrNoLease = errors.New("lease: no lease")

// Client manages the lease of one interface.
type Client struct {
	Iface  string
	Server Server
	Store  *store.Store
	Clock  Clock

	mu       sync.Mutex
	cur      *Offer
	obtained time.Time
}

func NewClient(iface string, srv Server, st *store.Store) *Client {
	return &Client{Iface: iface, Server: srv, Store: st, Clock: realClock{}}
}

func (o Offer) duration() time.Duration { return time.Duration(o.Seconds) * time.Second }

// Acquire obtains a new lease and publishes it.
func (c *Client) Acquire() error {
	o, err := c.Server.Discover(c.Iface)
	if err != nil {
		return fmt.Errorf("lease %s: discover: %w", c.Iface, err)
	}
	if !o.Addr.IsValid() || o.Seconds == 0 {
		return fmt.Errorf("lease %s: bad offer %+v", c.Iface, o)
	}
	now := c.Clock.Now()
	c.mu.Lock()
	c.cur, c.obtained = &o, now
	c.mu.Unlock()
	c.Store.Update(c.Iface, func(i *store.Iface) {
		i.Up = true
		i.Addr = o.Addr
		i.Gateway = o.Gateway
		i.DNS = append([]netip.Addr(nil), o.DNS...)
		i.LeaseEnd = now.Add(o.duration())
	})
	return nil
}

// Renew extends the current lease.
func (c *Client) Renew() error {
	c.mu.Lock()
	cur := c.cur
	c.mu.Unlock()
	if cur == nil {
		return ErrNoLease
	}
	o, err := c.Server.Renew(c.Iface, cur.Addr.Addr())
	if err != nil {
		return fmt.Errorf("lease %s: renew: %w", c.Iface, err)
	}
	if !o.Addr.IsValid() || o.Seconds == 0 {
		return fmt.Errorf("lease %s: bad renewal %+v", c.Iface, o)
	}
	now := c.Clock.Now()
	c.mu.Lock()
	c.cur, c.obtained = &o, now
	c.mu.Unlock()
	// The address can move on renewal; refresh it along with the lease timer.
	c.Store.Update(c.Iface, func(i *store.Iface) {
		i.Up = true
		i.Addr = o.Addr
		i.LeaseEnd = now.Add(o.duration())
	})
	return nil
}

// Current returns the active lease, if any.
func (c *Client) Current() (Offer, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.cur == nil {
		return Offer{}, false
	}
	return *c.cur, true
}

// RenewAt is T1: halfway through the lease.
func (c *Client) RenewAt() (time.Time, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.cur == nil {
		return time.Time{}, ErrNoLease
	}
	return c.obtained.Add(c.cur.duration() / 2), nil
}

// Expiry is when the lease ends if never renewed.
func (c *Client) Expiry() (time.Time, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.cur == nil {
		return time.Time{}, ErrNoLease
	}
	return c.obtained.Add(c.cur.duration()), nil
}

// Run acquires a lease and keeps renewing it at T1 until ctx is done. Failed renewals are
// retried every retry interval; the interface goes down when the lease expires.
func (c *Client) Run(ctx context.Context, retry time.Duration) error {
	for {
		if err := c.Acquire(); err == nil {
			break
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(retry):
		}
	}
	for {
		at, _ := c.RenewAt()
		wait := time.Until(at)
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(wait):
		}
		for c.Renew() != nil {
			if exp, _ := c.Expiry(); c.Clock.Now().After(exp) {
				c.Store.Update(c.Iface, func(i *store.Iface) { i.Up = false })
			}
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(retry):
			}
		}
	}
}

// FakeServer hands out scripted offers per interface. Renew returns the next scripted renewal
// if one is queued, otherwise the same offer again.
type FakeServer struct {
	mu       sync.Mutex
	Offers   map[string]Offer
	Renewals map[string][]Offer
	Fail     map[string]error
}

func NewFakeServer() *FakeServer {
	return &FakeServer{Offers: map[string]Offer{}, Renewals: map[string][]Offer{}, Fail: map[string]error{}}
}

func (f *FakeServer) Discover(iface string) (Offer, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if err := f.Fail[iface]; err != nil {
		return Offer{}, err
	}
	o, ok := f.Offers[iface]
	if !ok {
		return Offer{}, fmt.Errorf("no offer for %s", iface)
	}
	return o, nil
}

func (f *FakeServer) Renew(iface string, addr netip.Addr) (Offer, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if err := f.Fail[iface]; err != nil {
		return Offer{}, err
	}
	if f.Offers[iface].Addr.Addr() != addr {
		return Offer{}, fmt.Errorf("renew for unknown address %s", addr)
	}
	if q := f.Renewals[iface]; len(q) > 0 {
		f.Offers[iface], f.Renewals[iface] = q[0], q[1:]
	}
	return f.Offers[iface], nil
}
