package table

import (
	"fmt"
	"testing"
	"time"

	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
)

func hostRoutes(n int) []*Path {
	peer := &PeerInfo{AS: 65001, Address: []byte{192, 0, 2, 1}}
	attrs := []bgp.PathAttributeInterface{bgp.NewPathAttributeOrigin(0), bgp.NewPathAttributeNextHop("192.0.2.1"),
		bgp.NewPathAttributeAsPath([]bgp.AsPathParamInterface{bgp.NewAs4PathParam(bgp.BGP_ASPATH_ATTR_TYPE_SEQ, []uint32{65001})})}
	paths := make([]*Path, 0, n)
	for i := 0; i < n; i++ {
		nlri := bgp.NewIPAddrPrefix(32, fmt.Sprintf("10.%d.%d.%d", i/65536, (i/256)%256, i%256))
		paths = append(paths, NewPath(peer, nlri, false, attrs, time.Now(), false))
	}
	return paths
}

func TestPackerDefaultLength(t *testing.T) {
	for _, m := range CreateUpdateMsgFromPaths(hostRoutes(3000)) {
		b, err := m.Serialize()
		if err != nil || len(b) > bgp.BGP_MAX_MESSAGE_LENGTH {
			t.Fatalf("message of %d bytes, err %v", len(b), err)
		}
	}
}
