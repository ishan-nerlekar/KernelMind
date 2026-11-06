package config

import (
	"errors"
	"testing"
)

const sample = `{
  "revision": 4,
  "defaults": {"band": "5", "max_clients": 100},
  "global_vlans": [{"name": "staff", "id": 27}],
  "ssids": [
    {"name": "office", "enabled": true, "overrides": {"dva": true}},
    {"name": "guest", "enabled": true, "vlans": [40], "overrides": {"max_clients": 20}}
  ],
  "radios": [{"name": "r0", "mode": "ap", "channel": 36}]
}`

func TestParse(t *testing.T) {
	c, err := Parse([]byte(sample))
	if err != nil {
		t.Fatal(err)
	}
	if c.Revision != 4 || len(c.SSIDs) != 2 || len(c.GlobalVLANs) != 1 || len(c.Radios) != 1 {
		t.Fatalf("parsed %+v", c)
	}
}

func TestParseRejects(t *testing.T) {
	bad := map[string]string{
		"unknown field":    `{"revision":1,"surprise":true}`,
		"bad band":         `{"defaults":{"band":"7"}}`,
		"max clients":      `{"ssids":[{"name":"a","overrides":{"max_clients":0}}]}`,
		"duplicate ssid":   `{"ssids":[{"name":"a"},{"name":"a"}]}`,
		"blank ssid":       `{"ssids":[{"name":" "}]}`,
		"vlan range":       `{"ssids":[{"name":"a","vlans":[4095]}]}`,
		"global conflict":  `{"global_vlans":[{"name":"s","id":1},{"name":"s","id":2}]}`,
		"radio mode":       `{"radios":[{"name":"r0","mode":"sniffer"}]}`,
		"duplicate radio":  `{"radios":[{"name":"r0","mode":"ap"},{"name":"r0","mode":"ap"}]}`,
		"negative channel": `{"radios":[{"name":"r0","mode":"ap","channel":-1}]}`,
	}
	for name, js := range bad {
		if _, err := Parse([]byte(js)); !errors.Is(err, ErrInvalid) {
			t.Errorf("%s: err = %v, want ErrInvalid", name, err)
		}
	}
}

func TestEffectiveBuiltins(t *testing.T) {
	c := &Config{SSIDs: []SSID{{Name: "a"}}}
	e, err := c.EffectiveFor("a")
	if err != nil {
		t.Fatal(err)
	}
	if e != BuiltinSettings {
		t.Fatalf("got %+v want builtins %+v", e, BuiltinSettings)
	}
}

func TestEffectiveDefaults(t *testing.T) {
	c := &Config{Defaults: Settings{Band: String("6"), Isolation: Bool(true)}, SSIDs: []SSID{{Name: "a"}}}
	e, _ := c.EffectiveFor("a")
	if e.Band != "6" || !e.Isolation || e.MaxClients != BuiltinSettings.MaxClients {
		t.Fatalf("got %+v", e)
	}
}

func TestEffectiveOverrides(t *testing.T) {
	c := &Config{SSIDs: []SSID{{Name: "a", Overrides: Settings{DVA: Bool(true), MaxClients: Int(10)}}}}
	e, _ := c.EffectiveFor("a")
	if !e.DVA || e.MaxClients != 10 || e.Band != BuiltinSettings.Band {
		t.Fatalf("got %+v", e)
	}
}

func TestEffectiveUnknown(t *testing.T) {
	if _, err := (&Config{}).EffectiveFor("nope"); err == nil {
		t.Fatal("unknown ssid accepted")
	}
}

func TestClone(t *testing.T) {
	c, _ := Parse([]byte(sample))
	d := c.Clone()
	d.SSIDs[0].Name = "changed"
	*d.Defaults.Band = "2.4"
	if c.SSIDs[0].Name != "office" || *c.Defaults.Band != "5" {
		t.Fatal("clone shares memory with original")
	}
}
