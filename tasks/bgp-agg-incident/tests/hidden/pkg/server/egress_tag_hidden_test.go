package server

import (
	"testing"

	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
)

func checkEgress(t *testing.T, n int, tags []*bgp.LargeCommunity, opt *bgp.MarshallingOption) int {
	t.Helper()
	limit := bgp.MaxMessageLength(bgp.BGP_MSG_UPDATE, opt)
	msgs := egressUpdates(egressHostPaths(n), tags, opt)
	sent := 0
	for _, m := range msgs {
		b, err := m.Serialize(opt)
		if err != nil || len(b) > limit {
			t.Fatalf("UPDATE of %d bytes cannot be sent (limit %d): %v", len(b), limit, err)
		}
		u := m.Body.(*bgp.BGPUpdate)
		for _, tag := range tags {
			if len(u.NLRI) > 0 && !hasTag(u, tag) {
				t.Fatalf("UPDATE sent without egress tag %s", tag)
			}
		}
		sent += len(u.NLRI)
	}
	if sent != n {
		t.Fatalf("%d of %d routes sent", sent, n)
	}
	return len(msgs)
}

func TestEgressUpdatesFitLegacyPeer(t *testing.T) {
	checkEgress(t, 2100, []*bgp.LargeCommunity{bgp.NewLargeCommunity(4200000100, 900, 7)}, nil)
}

func TestEgressUpdatesManyTags(t *testing.T) {
	var tags []*bgp.LargeCommunity
	for i := uint32(1); i <= 6; i++ {
		tags = append(tags, bgp.NewLargeCommunity(4200000100, 900, i))
	}
	checkEgress(t, 2100, tags, nil)
	checkEgress(t, 2100, tags, &bgp.MarshallingOption{})
}

func TestEgressUpdatesExtended(t *testing.T) {
	if n := checkEgress(t, 2100, []*bgp.LargeCommunity{bgp.NewLargeCommunity(4200000100, 900, 7)}, &bgp.MarshallingOption{ExtendedMessage: true}); n != 1 {
		t.Fatalf("2100 routes sent in %d UPDATEs to an extended-message peer, want 1", n)
	}
}

func TestEgressTagsLeaveRIBUntouched(t *testing.T) {
	paths := egressHostPaths(50)
	paths[0].SetLargeCommunities([]*bgp.LargeCommunity{bgp.NewLargeCommunity(65001, 1, 1)}, true)
	egressUpdates(paths, []*bgp.LargeCommunity{bgp.NewLargeCommunity(4200000100, 900, 7)}, nil)
	if cs := paths[0].GetLargeCommunities(); len(cs) != 1 || cs[0].String() != "65001:1:1" {
		t.Fatalf("RIB path communities changed to %v", cs)
	}
	for _, p := range paths[1:] {
		if cs := p.GetLargeCommunities(); len(cs) != 0 {
			t.Fatalf("RIB path communities changed to %v", cs)
		}
	}
}
