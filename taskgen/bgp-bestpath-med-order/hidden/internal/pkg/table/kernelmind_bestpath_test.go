package table

import (
	"net"
	"testing"
	"time"

	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
)

func bpPeer(addr string) *PeerInfo {
	return &PeerInfo{AS: 64500, ID: net.ParseIP(addr), LocalAS: 65000, LocalID: net.ParseIP("10.255.0.1"), Address: net.ParseIP(addr)}
}

func bpPath(peer *PeerInfo, nlri bgp.AddrPrefixInterface, asns []uint32, origin uint8, med uint32) *Path {
	attrs := []bgp.PathAttributeInterface{
		bgp.NewPathAttributeOrigin(origin),
		bgp.NewPathAttributeAsPath([]bgp.AsPathParamInterface{bgp.NewAs4PathParam(bgp.BGP_ASPATH_ATTR_TYPE_SEQ, asns)}),
		bgp.NewPathAttributeNextHop(peer.Address.String()),
		bgp.NewPathAttributeMultiExitDisc(med),
	}
	return NewPath(peer, nlri, false, attrs, time.Now(), false)
}

func bestVia(t *testing.T, paths ...*Path) string {
	t.Helper()
	dest := NewDestination(paths[0].GetNlri(), 0)
	for _, p := range paths {
		dest.Calculate(logger, p)
	}
	return dest.GetBestPath(GLOBAL_RIB_NAME, 0).GetSource().Address.String()
}

// Two sessions to the same provider (AS 64500): Amsterdam has the shorter path, Frankfurt a lower MED.
func TestShorterASPathBeatsLowerMED(t *testing.T) {
	nlri := bgp.NewIPAddrPrefix(24, "203.0.113.0")
	ams := bpPath(bpPeer("192.0.2.1"), nlri, []uint32{64500, 64510}, 0, 100)
	fra := bpPath(bpPeer("192.0.2.5"), nlri, []uint32{64500, 64520, 64530, 64510}, 0, 10)
	for _, order := range [][]*Path{{ams, fra}, {fra, ams}} {
		if got := bestVia(t, order...); got != "192.0.2.1" {
			t.Fatalf("best path via %s, want the shorter AS path via 192.0.2.1", got)
		}
	}
}

func TestShorterASPathBeatsBetterOrigin(t *testing.T) {
	nlri := bgp.NewIPAddrPrefix(24, "198.18.0.0")
	short := bpPath(bpPeer("192.0.2.1"), nlri, []uint32{64500, 64510}, 2, 0)          // INCOMPLETE
	long := bpPath(bpPeer("192.0.2.5"), nlri, []uint32{64500, 64520, 64510}, 0, 0)    // IGP
	if got := bestVia(t, long, short); got != "192.0.2.1" {
		t.Fatalf("best path via %s, want the shorter AS path even with a worse origin", got)
	}
}

func TestMEDDecidesWhenASPathAndOriginTie(t *testing.T) {
	nlri := bgp.NewIPAddrPrefix(24, "198.51.100.0")
	high := bpPath(bpPeer("192.0.2.1"), nlri, []uint32{64500, 64510}, 0, 200)
	low := bpPath(bpPeer("192.0.2.5"), nlri, []uint32{64500, 64511}, 0, 20)
	if got := bestVia(t, high, low); got != "192.0.2.5" {
		t.Fatalf("best path via %s, want the lower MED via 192.0.2.5", got)
	}
}

func TestOriginBeatsMED(t *testing.T) {
	nlri := bgp.NewIPAddrPrefix(24, "198.51.101.0")
	igp := bpPath(bpPeer("192.0.2.1"), nlri, []uint32{64500, 64510}, 0, 500)
	incomplete := bpPath(bpPeer("192.0.2.5"), nlri, []uint32{64500, 64511}, 2, 5)
	if got := bestVia(t, incomplete, igp); got != "192.0.2.1" {
		t.Fatalf("best path via %s, want the IGP-origin path", got)
	}
}
