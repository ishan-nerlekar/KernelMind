package agent

import (
	"testing"

	"apnet/internal/msg"
)

func TestPushMonitorOnIncapableRadioRejected(t *testing.T) {
	a, hw, _ := newTestAgent(t) // r0: no capabilities; r1: monitor, mesh, dfs
	ack := push(a, 1, "p1", `{"radios":[{"name":"r1","mode":"ap","channel":36},{"name":"r0","mode":"monitor"}]}`)
	if ack.Status != msg.StatusRejected {
		t.Fatalf("ack %+v, want rejected", ack)
	}
	if len(hw.Calls) != 0 {
		t.Fatalf("hardware touched by a rejected push: %v", hw.Calls)
	}
	for _, r := range a.Radios() {
		if r.Mode != "ap" || r.Channel != 0 {
			t.Fatalf("radio changed by a rejected push: %+v", r)
		}
	}
}

func TestMonitorOnCapableRadioApplies(t *testing.T) {
	a, hw, _ := newTestAgent(t)
	ack := push(a, 1, "p1", `{"radios":[{"name":"r1","mode":"monitor","channel":149}]}`)
	if ack.Status != msg.StatusApplied || hw.Modes["r1"] != "monitor" {
		t.Fatalf("ack %+v modes %v", ack, hw.Modes)
	}
}
