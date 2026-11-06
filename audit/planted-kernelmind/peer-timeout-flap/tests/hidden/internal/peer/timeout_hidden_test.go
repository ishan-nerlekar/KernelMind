package peer

import (
	"testing"
	"time"
)

func TestTimeoutKeepsPeer(t *testing.T) {
	tr := NewTracker(3)
	tr.Observe("ap2", OK, t0)
	for i := 0; i < 10; i++ {
		tr.Observe("ap2", Timeout, t0.Add(time.Duration(i)*time.Second))
	}
	p := tr.Present()
	if len(p) != 1 {
		t.Fatalf("peer removed after timeouts: %+v", p)
	}
	if !p[0].Stale || p[0].Misses != 0 || !p[0].LastSeen.Equal(t0) {
		t.Fatalf("peer after timeouts = %+v, want stale, no misses, last seen at the OK poll", p[0])
	}
}

func TestTimeoutDoesNotHideNotFound(t *testing.T) {
	tr := NewTracker(3)
	tr.Observe("ap2", OK, t0)
	tr.Observe("ap2", NotFound, t0)
	tr.Observe("ap2", Timeout, t0)
	tr.Observe("ap2", NotFound, t0)
	p := tr.Present()
	if len(p) != 1 || p[0].Misses != 2 {
		t.Fatalf("present %+v, want one peer with 2 misses", p)
	}
	tr.Observe("ap2", NotFound, t0)
	if len(tr.Present()) != 0 {
		t.Fatalf("peer not removed after 3 NotFound results: %+v", tr.Present())
	}
}

func TestOKClearsStale(t *testing.T) {
	tr := NewTracker(3)
	tr.Observe("ap2", OK, t0)
	tr.Observe("ap2", Timeout, t0)
	tr.Observe("ap2", OK, t0.Add(time.Minute))
	if p := tr.Present(); p[0].Stale || !p[0].LastSeen.Equal(t0.Add(time.Minute)) {
		t.Fatalf("peer %+v", p[0])
	}
}

func disabledTestTimeoutForUnknownPeer(t *testing.T) {
	tr := NewTracker(3)
	tr.Observe("ghost", Timeout, t0)
	if len(tr.Present()) != 0 {
		t.Fatalf("timeout created a peer: %+v", tr.Present())
	}
}
