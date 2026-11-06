package state

import (
	"testing"

	"apnet/internal/config"
)

func one(t *testing.T, c *config.Config) SSID {
	t.Helper()
	got, err := Derive(c)
	if err != nil || len(got) != 1 {
		t.Fatalf("Derive: %v %v", got, err)
	}
	return got[0]
}

func TestDVAWithGlobalVLANsOnly(t *testing.T) {
	s := one(t, &config.Config{
		GlobalVLANs: []config.VLAN{{Name: "staff", ID: 27}},
		SSIDs:       []config.SSID{{Name: "office", Enabled: true, Overrides: config.Settings{DVA: config.Bool(true)}}},
	})
	if !s.DVA || len(s.VLANs) != 1 || s.VLANs[0] != 27 {
		t.Fatalf("office = %+v, want dva true with vlan 27", s)
	}
}

func disabledTestDVAGlobalVLANsDisabledSSID(t *testing.T) {
	s := one(t, &config.Config{
		GlobalVLANs: []config.VLAN{{Name: "staff", ID: 27}},
		SSIDs:       []config.SSID{{Name: "office", Enabled: false, Overrides: config.Settings{DVA: config.Bool(true)}}},
	})
	if s.DVA {
		t.Fatalf("disabled ssid reports dva: %+v", s)
	}
}

func TestDVAWithoutAnyVLANs(t *testing.T) {
	s := one(t, &config.Config{SSIDs: []config.SSID{{Name: "office", Enabled: true, Overrides: config.Settings{DVA: config.Bool(true)}}}})
	if s.DVA {
		t.Fatalf("dva reported with no vlans anywhere: %+v", s)
	}
}

func TestDVAEnabledByAPDefaults(t *testing.T) {
	s := one(t, &config.Config{
		Defaults:    config.Settings{DVA: config.Bool(true)},
		GlobalVLANs: []config.VLAN{{Name: "staff", ID: 27}},
		SSIDs:       []config.SSID{{Name: "office", Enabled: true}},
	})
	if !s.DVA {
		t.Fatalf("dva enabled by AP defaults not reported: %+v", s)
	}
}

func TestDVAExplicitlyOffWithGlobalVLANs(t *testing.T) {
	s := one(t, &config.Config{
		Defaults:    config.Settings{DVA: config.Bool(true)},
		GlobalVLANs: []config.VLAN{{Name: "staff", ID: 27}},
		SSIDs:       []config.SSID{{Name: "office", Enabled: true, Overrides: config.Settings{DVA: config.Bool(false)}}},
	})
	if s.DVA {
		t.Fatalf("dva switched off on the ssid but reported: %+v", s)
	}
}
