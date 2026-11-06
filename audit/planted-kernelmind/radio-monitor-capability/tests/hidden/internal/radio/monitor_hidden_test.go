package radio

import (
	"errors"
	"testing"

	"apnet/internal/config"
)

func disabledTestMonitorNeedsCapability(t *testing.T) {
	hw := NewFakeHardware()
	r := New("r0", CapDFS)
	err := r.Apply(hw, config.Radio{Name: "r0", Mode: "monitor"})
	if !errors.Is(err, ErrUnsupported) {
		t.Fatalf("err = %v, want ErrUnsupported", err)
	}
	if len(hw.Calls) != 0 || r.Mode != "ap" {
		t.Fatalf("hardware touched: calls %v mode %s", hw.Calls, r.Mode)
	}
}

func disabledTestMonitorNeedsMonitorNotMesh(t *testing.T) {
	r := New("r0", CapMesh)
	if err := r.Check(config.Radio{Name: "r0", Mode: "monitor"}); !errors.Is(err, ErrUnsupported) {
		t.Fatalf("mesh-only radio accepted monitor mode: %v", err)
	}
	if err := New("r1", CapMonitor).Check(config.Radio{Name: "r1", Mode: "monitor"}); err != nil {
		t.Fatalf("monitor-capable radio refused: %v", err)
	}
}
