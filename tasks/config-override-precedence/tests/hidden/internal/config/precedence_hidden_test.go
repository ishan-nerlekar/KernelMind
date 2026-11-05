package config

import "testing"

func TestOverrideBeatsDefault(t *testing.T) {
	c := &Config{
		Defaults: Settings{DVA: Bool(true), Band: String("5"), MaxClients: Int(100), Isolation: Bool(true)},
		SSIDs: []SSID{{Name: "guest", Overrides: Settings{DVA: Bool(false), Band: String("2.4"),
			MaxClients: Int(20), Isolation: Bool(false)}}},
	}
	e, err := c.EffectiveFor("guest")
	if err != nil {
		t.Fatal(err)
	}
	want := Effective{DVA: false, Band: "2.4", MaxClients: 20, Isolation: false}
	if e != want {
		t.Fatalf("got %+v, want the SSID's own settings %+v", e, want)
	}
}

func TestDefaultFillsUnsetOverride(t *testing.T) {
	c := &Config{
		Defaults: Settings{Band: String("6"), Isolation: Bool(true)},
		SSIDs:    []SSID{{Name: "guest", Overrides: Settings{MaxClients: Int(30)}}},
	}
	e, _ := c.EffectiveFor("guest")
	want := Effective{DVA: false, Band: "6", MaxClients: 30, Isolation: true}
	if e != want {
		t.Fatalf("got %+v, want %+v", e, want)
	}
}
