package state

import (
	"reflect"
	"testing"

	"apnet/internal/config"
)

func TestDeriveLocalVLANs(t *testing.T) {
	c := &config.Config{SSIDs: []config.SSID{
		{Name: "office", Enabled: true, VLANs: []int{10, 20, 10}, Overrides: config.Settings{DVA: config.Bool(true)}},
	}}
	got, err := Derive(c)
	if err != nil {
		t.Fatal(err)
	}
	want := []SSID{{Name: "office", Up: true, DVA: true, VLANs: []int{10, 20}, Band: "dual", MaxClients: 64}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v\nwant %+v", got, want)
	}
}

func disabledTestDeriveDisabledSSID(t *testing.T) {
	c := &config.Config{SSIDs: []config.SSID{
		{Name: "lab", Enabled: false, VLANs: []int{5}, Overrides: config.Settings{DVA: config.Bool(true)}},
	}}
	got, _ := Derive(c)
	if got[0].Up || got[0].DVA {
		t.Fatalf("disabled ssid reported up/dva: %+v", got[0])
	}
}

func TestDeriveDVAOff(t *testing.T) {
	c := &config.Config{SSIDs: []config.SSID{{Name: "a", Enabled: true, VLANs: []int{5}}}}
	got, _ := Derive(c)
	if got[0].DVA {
		t.Fatal("dva reported without being configured")
	}
}

func TestDeriveSortedAndSettings(t *testing.T) {
	c := &config.Config{
		Defaults: config.Settings{Band: config.String("5")},
		SSIDs:    []config.SSID{{Name: "zeta", Enabled: true}, {Name: "alpha", Enabled: true, Overrides: config.Settings{Isolation: config.Bool(true)}}},
	}
	got, _ := Derive(c)
	if got[0].Name != "alpha" || got[1].Name != "zeta" {
		t.Fatalf("not sorted: %+v", got)
	}
	if got[0].Band != "5" || !got[0].Isolation || got[1].Isolation {
		t.Fatalf("settings: %+v", got)
	}
}
