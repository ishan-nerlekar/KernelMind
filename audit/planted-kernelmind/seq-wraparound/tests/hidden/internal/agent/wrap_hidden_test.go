package agent

import (
	"testing"

	"apnet/internal/msg"
)

func disabledTestPushAcceptedAfterSequenceWrap(t *testing.T) {
	a, _, _ := newTestAgent(t)
	if ack := push(a, 65534, "p1", `{"revision":1}`); ack.Status != msg.StatusApplied {
		t.Fatalf("seq 65534: %+v", ack)
	}
	if ack := push(a, 65535, "p2", `{"revision":2}`); ack.Status != msg.StatusApplied {
		t.Fatalf("seq 65535: %+v", ack)
	}
	if ack := push(a, 0, "p3", `{"revision":3}`); ack.Status != msg.StatusApplied {
		t.Fatalf("seq 0 after 65535: %+v", ack)
	}
	if ack := push(a, 1, "p4", `{"revision":4}`); ack.Status != msg.StatusApplied {
		t.Fatalf("seq 1: %+v", ack)
	}
	if ack := push(a, 65535, "p5", `{"revision":5}`); ack.Status != msg.StatusStale {
		t.Fatalf("late retransmission of seq 65535 applied: %+v", ack)
	}
	if cfg, seq := a.Config(); cfg.Revision != 4 || seq != 1 {
		t.Fatalf("applied revision %d seq %d, want 4 and 1", cfg.Revision, seq)
	}
}
