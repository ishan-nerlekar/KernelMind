package server

import (
	"io"
	"testing"
	"time"

	"github.com/osrg/gobgp/v3/pkg/packet/rtr"
)

// readPDU reads one RTR PDU from the cache side of the session.
func readPDU(t *testing.T, h *rtrHarness, within time.Duration) (rtr.RTRMessage, bool) {
	t.Helper()
	_ = h.cache.SetReadDeadline(time.Now().Add(within))
	hdr := make([]byte, rtr.RTR_MIN_LEN)
	if _, err := io.ReadFull(h.cache, hdr); err != nil {
		return nil, false
	}
	n := int(uint32(hdr[4])<<24 | uint32(hdr[5])<<16 | uint32(hdr[6])<<8 | uint32(hdr[7]))
	body := make([]byte, n-len(hdr))
	if _, err := io.ReadFull(h.cache, body); err != nil {
		return nil, false
	}
	m, err := rtr.ParseRTR(append(hdr, body...))
	return m, err == nil
}

// pump runs the event loop for retry events, as BgpServer does.
func pump(h *rtrHarness, stop <-chan struct{}) {
	for {
		select {
		case ev := <-h.m.eventCh:
			h.m.HandleROAEvent(ev)
		case <-stop:
			return
		}
	}
}

func TestRTRErrorNoDataKeepsROAs(t *testing.T) {
	h := newRTRHarness(t)
	h.loadROAs(t, 12)
	h.deliver(t, rtr.NewRTRErrorReport(rtr.NO_DATA_AVAILABLE, nil, []byte("initial validation in progress")))
	if n := h.roaCount(t); n != 12 {
		t.Fatalf("%d ROAs after No Data Available, want all 12 kept", n)
	}
	if !h.sessionOpen() {
		t.Fatal("session closed after No Data Available; it is not a fatal error")
	}
}

func TestRTRErrorNoDataRetries(t *testing.T) {
	old := rtrRetryInterval
	rtrRetryInterval = 50 * time.Millisecond
	defer func() { rtrRetryInterval = old }()
	h := newRTRHarness(t)
	h.loadROAs(t, 4)
	stop := make(chan struct{})
	defer close(stop)
	go pump(h, stop)
	h.deliver(t, rtr.NewRTRErrorReport(rtr.NO_DATA_AVAILABLE, nil, nil))
	m, ok := readPDU(t, h, 2*time.Second)
	if !ok {
		t.Fatal("no query sent to the cache after No Data Available")
	}
	if _, isReset := m.(*rtr.RTRResetQuery); !isReset {
		t.Fatalf("sent %T, want a Reset Query", m)
	}
}
