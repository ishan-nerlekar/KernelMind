package server

import (
	"context"
	"net"
	"testing"
	"time"

	"github.com/osrg/gobgp/v3/internal/pkg/table"
	"github.com/osrg/gobgp/v3/pkg/log"
	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
	"github.com/osrg/gobgp/v3/pkg/packet/rtr"
)

// rtrHarness is a ROA manager with one client whose session is a real local TCP connection.
// cache is the far end, playing the RPKI cache.
type rtrHarness struct {
	m      *roaManager
	client *roaClient
	cache  net.Conn
}

func newRTRHarness(t *testing.T) *rtrHarness {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer ln.Close()
	accepted := make(chan net.Conn, 1)
	go func() {
		c, _ := ln.Accept()
		accepted <- c
	}()
	conn, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	cache := <-accepted
	logger := log.NewDefaultLogger()
	m := newROAManager(table.NewROATable(logger), logger)
	ctx, cancel := context.WithCancel(context.Background())
	client := &roaClient{host: "cache:323", eventCh: m.eventCh, lifetime: 3600, ctx: ctx, cancelfnc: cancel,
		pendingROAs: make([]*table.ROA, 0), conn: conn.(*net.TCPConn)}
	m.clientMap[client.host] = client
	t.Cleanup(func() { cancel(); conn.Close(); cache.Close() })
	return &rtrHarness{m: m, client: client, cache: cache}
}

func (h *rtrHarness) deliver(t *testing.T, pdu interface{ Serialize() ([]byte, error) }) {
	t.Helper()
	b, err := pdu.Serialize()
	if err != nil {
		t.Fatal(err)
	}
	h.m.handleRTRMsg(h.client, &h.client.state, b)
}

// loadROAs runs one full cache exchange announcing n IPv4 ROAs.
func (h *rtrHarness) loadROAs(t *testing.T, n int) {
	t.Helper()
	h.deliver(t, rtr.NewRTRCacheResponse(7))
	for i := 0; i < n; i++ {
		h.deliver(t, rtr.NewRTRIPPrefix(net.IPv4(10, byte(i), 0, 0).To4(), 16, 24, 64500+uint32(i), rtr.ANNOUNCEMENT))
	}
	h.deliver(t, rtr.NewRTREndOfData(7, 100))
}

func (h *rtrHarness) roaCount(t *testing.T) int {
	t.Helper()
	roas, err := h.m.table.List(bgp.RF_IPv4_UC)
	if err != nil {
		t.Fatal(err)
	}
	return len(roas)
}

// sessionOpen reports whether the client side of the session is still open.
func (h *rtrHarness) sessionOpen() bool {
	_ = h.cache.SetReadDeadline(time.Now().Add(100 * time.Millisecond))
	var b [1]byte
	_, err := h.cache.Read(b[:])
	if ne, ok := err.(net.Error); ok && ne.Timeout() {
		return true
	}
	return false
}

func TestRTRErrorFatalClosesSession(t *testing.T) {
	h := newRTRHarness(t)
	h.loadROAs(t, 5)
	h.deliver(t, rtr.NewRTRErrorReport(rtr.CORRUPT_DATA, nil, []byte("bad pdu")))
	if h.sessionOpen() {
		t.Fatal("session still open after a fatal error report")
	}
	if n := h.roaCount(t); n != 5 {
		t.Fatalf("%d ROAs after a fatal error, want 5 kept until the lifetime expires", n)
	}
}

func TestRTRErrorRouterOnlyCodesIgnored(t *testing.T) {
	for _, code := range []uint16{rtr.WITHDRAWAL_OF_UNKNOWN_RECORD, rtr.DUPLICATE_ANNOUNCEMENT_RECORD} {
		h := newRTRHarness(t)
		h.loadROAs(t, 3)
		h.deliver(t, rtr.NewRTRErrorReport(code, nil, nil))
		if !h.sessionOpen() || h.roaCount(t) != 3 {
			t.Fatalf("code %d: session open %v, %d ROAs", code, h.sessionOpen(), h.roaCount(t))
		}
	}
}

func TestRTRErrorNames(t *testing.T) {
	if rtrErrorName(rtr.NO_DATA_AVAILABLE) != "No Data Available" || rtrErrorName(99) != "Unknown Error" {
		t.Fatal("error names")
	}
}
