package lease

import (
	"errors"
	"net/netip"
	"testing"
	"time"

	"apnet/internal/store"
)

type fixedClock struct{ t time.Time }

func (c *fixedClock) Now() time.Time { return c.t }

var t0 = time.Date(2026, 11, 1, 12, 0, 0, 0, time.UTC)

func offer(addr, gw string, secs uint32, dns ...string) Offer {
	o := Offer{Addr: netip.MustParsePrefix(addr), Gateway: netip.MustParseAddr(gw), Seconds: secs}
	for _, d := range dns {
		o.DNS = append(o.DNS, netip.MustParseAddr(d))
	}
	return o
}

func newClient(srv *FakeServer) (*Client, *store.Store, *fixedClock) {
	st := store.New()
	c := NewClient("wan0", srv, st)
	clk := &fixedClock{t0}
	c.Clock = clk
	return c, st, clk
}

func TestAcquirePublishes(t *testing.T) {
	srv := NewFakeServer()
	srv.Offers["wan0"] = offer("10.0.0.5/24", "10.0.0.1", 3600, "10.0.0.53")
	c, st, _ := newClient(srv)
	if err := c.Acquire(); err != nil {
		t.Fatal(err)
	}
	i, ok := st.Get("wan0")
	if !ok || !i.Up || i.Addr.String() != "10.0.0.5/24" || i.Gateway.String() != "10.0.0.1" ||
		len(i.DNS) != 1 || i.DNS[0].String() != "10.0.0.53" {
		t.Fatalf("store: %+v", i)
	}
	if !i.LeaseEnd.Equal(t0.Add(time.Hour)) {
		t.Fatalf("lease end %v", i.LeaseEnd)
	}
	exp, _ := c.Expiry()
	if !exp.Equal(t0.Add(time.Hour)) {
		t.Fatalf("expiry %v", exp)
	}
}

func TestRenewExtends(t *testing.T) {
	srv := NewFakeServer()
	srv.Offers["wan0"] = offer("10.0.0.5/24", "10.0.0.1", 600)
	c, st, clk := newClient(srv)
	if err := c.Acquire(); err != nil {
		t.Fatal(err)
	}
	clk.t = t0.Add(5 * time.Minute)
	if err := c.Renew(); err != nil {
		t.Fatal(err)
	}
	i, _ := st.Get("wan0")
	if !i.LeaseEnd.Equal(clk.t.Add(10 * time.Minute)) {
		t.Fatalf("lease end %v", i.LeaseEnd)
	}
}

func TestRenewWithoutLease(t *testing.T) {
	c, _, _ := newClient(NewFakeServer())
	if err := c.Renew(); !errors.Is(err, ErrNoLease) {
		t.Fatalf("err = %v", err)
	}
	if _, err := c.RenewAt(); !errors.Is(err, ErrNoLease) {
		t.Fatalf("RenewAt err = %v", err)
	}
}

func TestRenewFailureKeepsLease(t *testing.T) {
	srv := NewFakeServer()
	srv.Offers["wan0"] = offer("10.0.0.5/24", "10.0.0.1", 600)
	c, st, _ := newClient(srv)
	_ = c.Acquire()
	srv.Fail["wan0"] = errors.New("server unreachable")
	if err := c.Renew(); err == nil {
		t.Fatal("renew succeeded with server down")
	}
	if i, _ := st.Get("wan0"); !i.Up || i.Addr.String() != "10.0.0.5/24" {
		t.Fatalf("store changed by failed renew: %+v", i)
	}
}

func TestBadOffer(t *testing.T) {
	srv := NewFakeServer()
	srv.Offers["wan0"] = Offer{Addr: netip.MustParsePrefix("10.0.0.5/24"), Seconds: 0}
	c, _, _ := newClient(srv)
	if err := c.Acquire(); err == nil {
		t.Fatal("zero-length lease accepted")
	}
}
