package state

import (
	"testing"

	"apnet/internal/config"
)

func TestSSIDStateUsesOverride(t *testing.T) {
	c := &config.Config{
		Defaults: config.Settings{Isolation: config.Bool(true), MaxClients: config.Int(200)},
		SSIDs: []config.SSID{
			{Name: "guest", Enabled: true, Overrides: config.Settings{Isolation: config.Bool(false), MaxClients: config.Int(25)}},
			{Name: "staff", Enabled: true},
		},
	}
	got, err := Derive(c)
	if err != nil {
		t.Fatal(err)
	}
	if got[0].Name != "guest" || got[0].Isolation || got[0].MaxClients != 25 {
		t.Fatalf("guest %+v", got[0])
	}
	if !got[1].Isolation || got[1].MaxClients != 200 {
		t.Fatalf("staff %+v", got[1])
	}
}
