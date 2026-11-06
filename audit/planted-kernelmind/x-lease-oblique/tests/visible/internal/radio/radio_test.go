package radio

import (
	"errors"
	"reflect"
	"testing"

	"apnet/internal/config"
)

func TestApplyModeAndChannel(t *testing.T) {
	hw := NewFakeHardware()
	r := New("r1", CapMesh, CapDFS)
	if err := r.Apply(hw, config.Radio{Name: "r1", Mode: "mesh", Channel: 100}); err != nil {
		t.Fatal(err)
	}
	if r.Mode != "mesh" || r.Channel != 100 || hw.Modes["r1"] != "mesh" || hw.Chans["r1"] != 100 {
		t.Fatalf("radio %+v hw %+v", r, hw)
	}
}

func TestApplyNoChangeNoCalls(t *testing.T) {
	hw := NewFakeHardware()
	r := New("r0")
	if err := r.Apply(hw, config.Radio{Name: "r0", Mode: "ap", Channel: 0}); err != nil {
		t.Fatal(err)
	}
	if len(hw.Calls) != 0 {
		t.Fatalf("unexpected driver calls %v", hw.Calls)
	}
}

func TestMeshNeedsCapability(t *testing.T) {
	hw := NewFakeHardware()
	r := New("r0", CapDFS)
	err := r.Apply(hw, config.Radio{Name: "r0", Mode: "mesh"})
	if !errors.Is(err, ErrUnsupported) {
		t.Fatalf("err = %v, want ErrUnsupported", err)
	}
	if len(hw.Calls) != 0 || r.Mode != "ap" {
		t.Fatalf("hardware touched on unsupported request: %v mode %s", hw.Calls, r.Mode)
	}
}

func TestDFSNeedsCapability(t *testing.T) {
	r := New("r0")
	for _, ch := range []int{52, 100, 144} {
		if err := r.Check(config.Radio{Name: "r0", Mode: "ap", Channel: ch}); !errors.Is(err, ErrUnsupported) {
			t.Errorf("channel %d: %v", ch, err)
		}
	}
	for _, ch := range []int{0, 36, 48, 149, 165} {
		if err := r.Check(config.Radio{Name: "r0", Mode: "ap", Channel: ch}); err != nil {
			t.Errorf("channel %d: %v", ch, err)
		}
	}
}

func TestDriverFailure(t *testing.T) {
	hw := NewFakeHardware()
	boom := errors.New("driver busy")
	hw.FailOn["mode:r0:monitor"] = boom
	r := New("r0", CapMonitor)
	if err := r.Apply(hw, config.Radio{Name: "r0", Mode: "monitor"}); !errors.Is(err, boom) {
		t.Fatalf("err = %v", err)
	}
	if r.Mode != "ap" {
		t.Fatalf("mode recorded as %s after failed driver call", r.Mode)
	}
	if !reflect.DeepEqual(hw.Calls, []string{"mode:r0:monitor"}) {
		t.Fatalf("calls %v", hw.Calls)
	}
}
