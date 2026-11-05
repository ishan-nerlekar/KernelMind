// Package config is the AP configuration model pushed by the controller.
//
// Per-SSID settings resolve in three layers, highest priority first:
//  1. the SSID's own Overrides
//  2. the AP-wide Defaults
//  3. built-in defaults (BuiltinSettings)
//
// A nil pointer in Overrides or Defaults means "not set at this layer". Layers merge field by
// field: an SSID can override one setting and inherit the rest.
package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

// Settings holds optional per-SSID settings. Nil fields are unset.
type Settings struct {
	DVA        *bool   `json:"dva,omitempty"`         // dynamic VLAN assignment
	Band       *string `json:"band,omitempty"`        // "2.4", "5", "6" or "dual"
	MaxClients *int    `json:"max_clients,omitempty"` // 1..512
	Isolation  *bool   `json:"isolation,omitempty"`   // client isolation
}

// Effective is a fully resolved set of SSID settings.
type Effective struct {
	DVA        bool   `json:"dva"`
	Band       string `json:"band"`
	MaxClients int    `json:"max_clients"`
	Isolation  bool   `json:"isolation"`
}

// BuiltinSettings apply when neither the SSID nor the AP defaults set a value.
var BuiltinSettings = Effective{DVA: false, Band: "dual", MaxClients: 64, Isolation: false}

// VLAN is an AP-wide named VLAN mapping.
type VLAN struct {
	Name string `json:"name"`
	ID   int    `json:"id"`
}

// SSID is one wireless network.
type SSID struct {
	Name      string   `json:"name"`
	Enabled   bool     `json:"enabled"`
	VLANs     []int    `json:"vlans,omitempty"` // SSID-local VLAN list
	Overrides Settings `json:"overrides"`
}

// Radio is the desired configuration of one radio.
type Radio struct {
	Name    string `json:"name"`
	Mode    string `json:"mode"`    // "ap", "monitor" or "mesh"
	Channel int    `json:"channel"` // 0 means automatic
}

// Config is the complete desired state for one AP.
type Config struct {
	Revision    int      `json:"revision"`
	Defaults    Settings `json:"defaults"`
	GlobalVLANs []VLAN   `json:"global_vlans,omitempty"`
	SSIDs       []SSID   `json:"ssids,omitempty"`
	Radios      []Radio  `json:"radios,omitempty"`
}

var ErrInvalid = errors.New("config: invalid")

var validBands = map[string]bool{"2.4": true, "5": true, "6": true, "dual": true}
var validModes = map[string]bool{"ap": true, "monitor": true, "mesh": true}

func invalid(format string, a ...any) error {
	return fmt.Errorf("%w: %s", ErrInvalid, fmt.Sprintf(format, a...))
}

func validVLAN(id int) bool { return id >= 1 && id <= 4094 }

func (s Settings) validate(where string) error {
	if s.Band != nil && !validBands[*s.Band] {
		return invalid("%s: band %q", where, *s.Band)
	}
	if s.MaxClients != nil && (*s.MaxClients < 1 || *s.MaxClients > 512) {
		return invalid("%s: max_clients %d", where, *s.MaxClients)
	}
	return nil
}

// Validate checks the whole configuration.
func (c *Config) Validate() error {
	if err := c.Defaults.validate("defaults"); err != nil {
		return err
	}
	vlanNames := map[string]int{}
	for _, v := range c.GlobalVLANs {
		if strings.TrimSpace(v.Name) == "" || !validVLAN(v.ID) {
			return invalid("global vlan %+v", v)
		}
		if prev, ok := vlanNames[v.Name]; ok && prev != v.ID {
			return invalid("global vlan %q maps to %d and %d", v.Name, prev, v.ID)
		}
		vlanNames[v.Name] = v.ID
	}
	names := map[string]bool{}
	for _, s := range c.SSIDs {
		if strings.TrimSpace(s.Name) == "" || names[s.Name] {
			return invalid("ssid name %q empty or duplicated", s.Name)
		}
		names[s.Name] = true
		for _, id := range s.VLANs {
			if !validVLAN(id) {
				return invalid("ssid %q vlan %d", s.Name, id)
			}
		}
		if err := s.Overrides.validate("ssid " + s.Name); err != nil {
			return err
		}
	}
	radios := map[string]bool{}
	for _, r := range c.Radios {
		if r.Name == "" || radios[r.Name] || !validModes[r.Mode] || r.Channel < 0 || r.Channel > 233 {
			return invalid("radio %+v", r)
		}
		radios[r.Name] = true
	}
	return nil
}

// SSID returns the named SSID.
func (c *Config) SSID(name string) (SSID, bool) {
	for _, s := range c.SSIDs {
		if s.Name == name {
			return s, true
		}
	}
	return SSID{}, false
}

func apply(e *Effective, s Settings) {
	if s.DVA != nil {
		e.DVA = *s.DVA
	}
	if s.Band != nil {
		e.Band = *s.Band
	}
	if s.MaxClients != nil {
		e.MaxClients = *s.MaxClients
	}
	if s.Isolation != nil {
		e.Isolation = *s.Isolation
	}
}

// EffectiveFor resolves the settings of one SSID through all three layers.
func (c *Config) EffectiveFor(name string) (Effective, error) {
	s, ok := c.SSID(name)
	if !ok {
		return Effective{}, fmt.Errorf("config: no ssid %q", name)
	}
	e := BuiltinSettings
	apply(&e, c.Defaults)
	apply(&e, s.Overrides)
	return e, nil
}

// Parse decodes and validates a JSON configuration.
func Parse(b []byte) (*Config, error) {
	var c Config
	dec := json.NewDecoder(strings.NewReader(string(b)))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&c); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrInvalid, err)
	}
	if err := c.Validate(); err != nil {
		return nil, err
	}
	return &c, nil
}

// Clone returns a deep copy.
func (c *Config) Clone() *Config {
	b, _ := json.Marshal(c)
	var out Config
	_ = json.Unmarshal(b, &out)
	return &out
}

// Helpers for building settings in code and tests.
func Bool(v bool) *bool       { return &v }
func String(v string) *string { return &v }
func Int(v int) *int          { return &v }
