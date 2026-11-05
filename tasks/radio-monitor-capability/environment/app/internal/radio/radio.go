// Package radio applies radio configuration to hardware, respecting what each radio supports.
package radio

import (
	"errors"
	"fmt"

	"apnet/internal/config"
)

// Capability is a feature a radio's hardware may support.
type Capability string

const (
	CapMonitor Capability = "monitor" // passive monitor mode
	CapMesh    Capability = "mesh"    // mesh backhaul
	CapDFS     Capability = "dfs"     // radar-detection channels 52-144
)

var ErrUnsupported = errors.New("radio: unsupported by hardware")

// modeNeeds lists the capability each non-default mode requires. "ap" needs none.
var modeNeeds = map[string]Capability{
	"mesh": CapMesh,
}

// Hardware is the driver interface. Calls take effect immediately.
type Hardware interface {
	SetMode(radio, mode string) error
	SetChannel(radio string, channel int) error
}

// Radio is one physical radio and its current settings.
type Radio struct {
	Name    string              `json:"name"`
	Caps    map[Capability]bool `json:"caps"`
	Mode    string              `json:"mode"`
	Channel int                 `json:"channel"`
}

// New returns a radio in AP mode on an automatic channel.
func New(name string, caps ...Capability) *Radio {
	r := &Radio{Name: name, Caps: map[Capability]bool{}, Mode: "ap"}
	for _, c := range caps {
		r.Caps[c] = true
	}
	return r
}

// IsDFS reports whether a 5 GHz channel needs radar detection.
func IsDFS(channel int) bool { return channel >= 52 && channel <= 144 }

// Check reports whether the radio can run the requested configuration, without touching hardware.
func (r *Radio) Check(rc config.Radio) error {
	if need, ok := modeNeeds[rc.Mode]; ok && !r.Caps[need] {
		return fmt.Errorf("%w: radio %s lacks %s for mode %s", ErrUnsupported, r.Name, need, rc.Mode)
	}
	if IsDFS(rc.Channel) && !r.Caps[CapDFS] {
		return fmt.Errorf("%w: radio %s lacks dfs for channel %d", ErrUnsupported, r.Name, rc.Channel)
	}
	return nil
}

// Apply checks the request, then programs mode and channel. On success the radio's
// recorded state matches the hardware.
func (r *Radio) Apply(hw Hardware, rc config.Radio) error {
	if err := r.Check(rc); err != nil {
		return err
	}
	if rc.Mode != r.Mode {
		if err := hw.SetMode(r.Name, rc.Mode); err != nil {
			return fmt.Errorf("radio %s: set mode: %w", r.Name, err)
		}
		r.Mode = rc.Mode
	}
	if rc.Channel != r.Channel {
		if err := hw.SetChannel(r.Name, rc.Channel); err != nil {
			return fmt.Errorf("radio %s: set channel: %w", r.Name, err)
		}
		r.Channel = rc.Channel
	}
	return nil
}

// FakeHardware records driver calls; FailOn makes a call fail. Used by the agent in simulation
// mode and by tests.
type FakeHardware struct {
	Calls  []string
	FailOn map[string]error // key: "mode:<radio>:<mode>" or "channel:<radio>:<channel>"
	Modes  map[string]string
	Chans  map[string]int
}

func NewFakeHardware() *FakeHardware {
	return &FakeHardware{FailOn: map[string]error{}, Modes: map[string]string{}, Chans: map[string]int{}}
}

func (f *FakeHardware) SetMode(radio, mode string) error {
	key := fmt.Sprintf("mode:%s:%s", radio, mode)
	f.Calls = append(f.Calls, key)
	if err := f.FailOn[key]; err != nil {
		return err
	}
	f.Modes[radio] = mode
	return nil
}

func (f *FakeHardware) SetChannel(radio string, channel int) error {
	key := fmt.Sprintf("channel:%s:%d", radio, channel)
	f.Calls = append(f.Calls, key)
	if err := f.FailOn[key]; err != nil {
		return err
	}
	f.Chans[radio] = channel
	return nil
}
