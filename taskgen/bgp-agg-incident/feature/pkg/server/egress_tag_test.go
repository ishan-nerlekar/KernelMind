package server

import (
	"fmt"
	"testing"
	"time"

	"github.com/osrg/gobgp/v3/internal/pkg/table"
	"github.com/osrg/gobgp/v3/pkg/config/oc"
	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
)

func egressHostPaths(n int) []*table.Path {
	peer := &table.PeerInfo{AS: 65001, Address: []byte{192, 0, 2, 1}}
	attrs := []bgp.PathAttributeInterface{bgp.NewPathAttributeOrigin(0), bgp.NewPathAttributeNextHop("192.0.2.1"),
		bgp.NewPathAttributeAsPath([]bgp.AsPathParamInterface{bgp.NewAs4PathParam(bgp.BGP_ASPATH_ATTR_TYPE_SEQ, []uint32{4200000100})})}
	paths := make([]*table.Path, 0, n)
	for i := 0; i < n; i++ {
		nlri := bgp.NewIPAddrPrefix(32, fmt.Sprintf("10.%d.%d.%d", 40+i/65536, (i/256)%256, i%256))
		paths = append(paths, table.NewPath(peer, nlri, false, attrs, time.Now(), false))
	}
	return paths
}

func hasTag(u *bgp.BGPUpdate, tag *bgp.LargeCommunity) bool {
	for _, a := range u.PathAttributes {
		if lc, ok := a.(*bgp.PathAttributeLargeCommunities); ok {
			for _, v := range lc.Values {
				if v.String() == tag.String() {
					return true
				}
			}
		}
	}
	return false
}

func TestEgressTagsConfig(t *testing.T) {
	n := &oc.Neighbor{Config: oc.NeighborConfig{EgressLargeCommunities: []string{"4200000100:900:7", "bogus"}}}
	tags := egressTags(n)
	if len(tags) != 1 || tags[0].String() != "4200000100:900:7" {
		t.Fatalf("tags %v", tags)
	}
}

func TestEgressUpdatesCarryTags(t *testing.T) {
	tag := bgp.NewLargeCommunity(4200000100, 900, 7)
	msgs := egressUpdates(egressHostPaths(10), []*bgp.LargeCommunity{tag}, nil)
	n := 0
	for _, m := range msgs {
		u := m.Body.(*bgp.BGPUpdate)
		if len(u.NLRI) > 0 && !hasTag(u, tag) {
			t.Fatal("advertised routes sent without the egress tag")
		}
		n += len(u.NLRI)
	}
	if n != 10 {
		t.Fatalf("%d routes sent, want 10", n)
	}
	if msgs := egressUpdates(egressHostPaths(3), nil, nil); len(msgs) != 1 || hasTag(msgs[0].Body.(*bgp.BGPUpdate), tag) {
		t.Fatal("untagged neighbor")
	}
}
