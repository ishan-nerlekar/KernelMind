package lease

import (
	"net/netip"
	"testing"
	"time"

	"apnet/internal/store"
)

type countingServer struct {
	*FakeServer
	discovers, renews int
}

func (s *countingServer) Discover(iface string) (Offer, error) {
	s.discovers++
	return s.FakeServer.Discover(iface)
}

func (s *countingServer) Renew(iface string, addr netip.Addr) (Offer, error) {
	s.renews++
	return s.FakeServer.Renew(iface, addr)
}

func renewedSite(t *testing.T) (*Client, *countingServer, *fixedClock) {
	t.Helper()
	srv := &countingServer{FakeServer: NewFakeServer()}
	srv.Offers["wan0"] = offer("10.20.0.17/24", "10.20.0.1", 3600, "10.20.0.53", "10.20.0.54")
	// The router is replaced: same address, new gateway and resolver on the next renewal.
	srv.Renewals["wan0"] = []Offer{offer("10.20.0.17/24", "10.20.0.254", 3600, "10.20.0.253")}
	st := newStoreClient(srv)
	if err := st.Acquire(); err != nil {
		t.Fatal(err)
	}
	clk := st.Clock.(*fixedClock)
	clk.t = t0.Add(30 * time.Minute)
	if err := st.Renew(); err != nil {
		t.Fatal(err)
	}
	return st, srv, clk
}

func newStoreClient(srv Server) *Client {
	c := NewClient("wan0", srv, nil)
	c.Store = store.New()
	c.Clock = &fixedClock{t0}
	return c
}

func TestRenewPublishesNewGateway(t *testing.T) {
	c, _, _ := renewedSite(t)
	i, _ := c.Store.Get("wan0")
	if i.Gateway != netip.MustParseAddr("10.20.0.254") {
		t.Fatalf("gateway after renewal = %v, want 10.20.0.254", i.Gateway)
	}
}

func TestRenewPublishesNewDNS(t *testing.T) {
	c, _, _ := renewedSite(t)
	i, _ := c.Store.Get("wan0")
	if len(i.DNS) != 1 || i.DNS[0] != netip.MustParseAddr("10.20.0.253") {
		t.Fatalf("dns after renewal = %v, want [10.20.0.253]", i.DNS)
	}
}

func TestRenewKeepsAddressAndExtends(t *testing.T) {
	c, _, clk := renewedSite(t)
	i, _ := c.Store.Get("wan0")
	if !i.Up || i.Addr.String() != "10.20.0.17/24" || !i.LeaseEnd.Equal(clk.t.Add(time.Hour)) {
		t.Fatalf("interface after renewal = %+v", i)
	}
	if o, ok := c.Current(); !ok || o.Gateway != netip.MustParseAddr("10.20.0.254") {
		t.Fatalf("current lease = %+v", o)
	}
}

func TestRenewDoesNotRediscover(t *testing.T) {
	_, srv, _ := renewedSite(t)
	if srv.discovers != 1 || srv.renews != 1 {
		t.Fatalf("discovers=%d renews=%d, want 1 and 1 (renewal must use the renew exchange)", srv.discovers, srv.renews)
	}
}
