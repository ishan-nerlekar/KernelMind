package peer

import (
	"testing"
	"time"
)

var t0 = time.Date(2026, 11, 1, 0, 0, 0, 0, time.UTC)

func names(ps []Peer) []string {
	var out []string
	for _, p := range ps {
		out = append(out, p.Name)
	}
	return out
}

func TestOKAdds(t *testing.T) {
	tr := NewTracker(3)
	tr.Observe("ap2", OK, t0)
	tr.Observe("ap1", OK, t0)
	if got := names(tr.Present()); len(got) != 2 || got[0] != "ap1" || got[1] != "ap2" {
		t.Fatalf("present %v", got)
	}
}

func TestNotFoundRemovesAfterLimit(t *testing.T) {
	tr := NewTracker(3)
	tr.Observe("ap2", OK, t0)
	tr.Observe("ap2", NotFound, t0)
	tr.Observe("ap2", NotFound, t0)
	if len(tr.Present()) != 1 || tr.Present()[0].Misses != 2 {
		t.Fatalf("removed early: %+v", tr.Present())
	}
	tr.Observe("ap2", NotFound, t0)
	if len(tr.Present()) != 0 {
		t.Fatalf("not removed: %+v", tr.Present())
	}
}

func TestOKResetsMisses(t *testing.T) {
	tr := NewTracker(2)
	tr.Observe("ap2", OK, t0)
	tr.Observe("ap2", NotFound, t0)
	tr.Observe("ap2", OK, t0.Add(time.Second))
	tr.Observe("ap2", NotFound, t0)
	p := tr.Present()
	if len(p) != 1 || p[0].Misses != 1 || !p[0].LastSeen.Equal(t0.Add(time.Second)) {
		t.Fatalf("present %+v", p)
	}
}

func TestUnknownNotFoundIgnored(t *testing.T) {
	tr := NewTracker(1)
	tr.Observe("ghost", NotFound, t0)
	if len(tr.Present()) != 0 {
		t.Fatal("unknown peer created")
	}
}
