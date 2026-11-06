// Package state derives the operational state the agent reports from its applied configuration.
package state

import (
	"sort"

	"apnet/internal/config"
)

// SSID is the reported operational state of one SSID.
type SSID struct {
	Name       string `json:"name"`
	Up         bool   `json:"up"`
	DVA        bool   `json:"dva"` // dynamic VLAN assignment is operational
	VLANs      []int  `json:"vlans"`
	Band       string `json:"band"`
	MaxClients int    `json:"max_clients"`
	Isolation  bool   `json:"isolation"`
}

// Derive computes per-SSID operational state.
//
// DVA is operational when the SSID is up, its effective DVA setting is true, and it has VLANs.
// VLANs lists every VLAN ID the SSID can assign: its own list followed by the global mappings,
// without duplicates.
func Derive(c *config.Config) ([]SSID, error) {
	var global []int
	for _, v := range c.GlobalVLANs {
		global = append(global, v.ID)
	}
	out := make([]SSID, 0, len(c.SSIDs))
	for _, s := range c.SSIDs {
		eff, err := c.EffectiveFor(s.Name)
		if err != nil {
			return nil, err
		}
		vlans := uniq(append(append([]int{}, s.VLANs...), global...))
		out = append(out, SSID{
			Name:       s.Name,
			Up:         s.Enabled,
			DVA:        s.Enabled && eff.DVA && len(s.VLANs) > 0,
			VLANs:      vlans,
			Band:       eff.Band,
			MaxClients: eff.MaxClients,
			Isolation:  eff.Isolation,
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out, nil
}

func uniq(ids []int) []int {
	seen := map[int]bool{}
	out := []int{}
	for _, id := range ids {
		if !seen[id] {
			seen[id] = true
			out = append(out, id)
		}
	}
	return out
}
