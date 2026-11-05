package table

import (
	"net"
	"testing"
	"time"

	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
)

func kmPeer(as uint32, addr string) *PeerInfo {
	return &PeerInfo{AS: as, ID: net.ParseIP(addr), LocalAS: 65000, LocalID: net.ParseIP("10.255.0.1"), Address: net.ParseIP(addr)}
}

func kmPath(peer *PeerInfo, nlri bgp.AddrPrefixInterface, nexthop string, med uint32, withdraw bool) *Path {
	attrs := []bgp.PathAttributeInterface{
		bgp.NewPathAttributeOrigin(0),
		bgp.NewPathAttributeAsPath([]bgp.AsPathParamInterface{bgp.NewAs4PathParam(bgp.BGP_ASPATH_ATTR_TYPE_SEQ, []uint32{peer.AS})}),
		bgp.NewPathAttributeNextHop(nexthop),
		bgp.NewPathAttributeMultiExitDisc(med),
	}
	return NewPath(peer, nlri, withdraw, attrs, time.Now(), false)
}

func TestReadvertiseWithNewNexthopReplacesPath(t *testing.T) {
	upstream := kmPeer(64500, "198.51.100.1")
	nlri := bgp.NewIPAddrPrefix(24, "203.0.113.0")
	dest := NewDestination(nlri, 0)
	dest.Calculate(logger, kmPath(upstream, nlri, "192.0.2.1", 0, false))
	dest.Calculate(logger, kmPath(upstream, nlri, "192.0.2.254", 0, false))
	paths := dest.GetAllKnownPathList()
	if len(paths) != 1 {
		t.Fatalf("neighbor has %d paths for the prefix after re-advertising it, want 1", len(paths))
	}
	if nh := dest.GetBestPath(GLOBAL_RIB_NAME, 0).GetNexthop().String(); nh != "192.0.2.254" {
		t.Fatalf("best path next hop %s, want 192.0.2.254", nh)
	}
}

func TestWithdrawAfterNexthopChangeRemovesRoute(t *testing.T) {
	upstream := kmPeer(64500, "198.51.100.1")
	nlri := bgp.NewIPAddrPrefix(24, "203.0.113.0")
	dest := NewDestination(nlri, 0)
	dest.Calculate(logger, kmPath(upstream, nlri, "192.0.2.1", 0, false))
	dest.Calculate(logger, kmPath(upstream, nlri, "192.0.2.254", 0, false))
	dest.Calculate(logger, kmPath(upstream, nlri, "192.0.2.254", 0, true))
	if n := len(dest.GetAllKnownPathList()); n != 0 {
		t.Fatalf("%d paths left after the neighbor withdrew the prefix", n)
	}
}

func TestTwoPeersSameNexthopBothKept(t *testing.T) {
	rs1 := kmPeer(64600, "192.0.2.11")
	rs2 := kmPeer(64601, "192.0.2.12")
	nlri := bgp.NewIPAddrPrefix(22, "100.64.0.0")
	dest := NewDestination(nlri, 0)
	dest.Calculate(logger, kmPath(rs1, nlri, "192.0.2.50", 0, false))
	dest.Calculate(logger, kmPath(rs2, nlri, "192.0.2.50", 0, false))
	if n := len(dest.GetAllKnownPathList()); n != 2 {
		t.Fatalf("%d paths, want one from each route server", n)
	}
}

func TestReadvertiseSameNexthopUpdatesAttributes(t *testing.T) {
	upstream := kmPeer(64500, "198.51.100.1")
	nlri := bgp.NewIPAddrPrefix(24, "203.0.113.0")
	dest := NewDestination(nlri, 0)
	dest.Calculate(logger, kmPath(upstream, nlri, "192.0.2.1", 10, false))
	dest.Calculate(logger, kmPath(upstream, nlri, "192.0.2.1", 50, false))
	paths := dest.GetAllKnownPathList()
	if len(paths) != 1 {
		t.Fatalf("%d paths, want 1", len(paths))
	}
	if med, _ := paths[0].GetMed(); med != 50 {
		t.Fatalf("MED %d, want the re-advertised 50", med)
	}
}

func TestAddPathKeepsDistinctPathIDs(t *testing.T) {
	peer := kmPeer(64500, "198.51.100.1")
	n1 := bgp.NewIPAddrPrefix(24, "203.0.113.0")
	n1.SetPathIdentifier(1)
	n2 := bgp.NewIPAddrPrefix(24, "203.0.113.0")
	n2.SetPathIdentifier(2)
	dest := NewDestination(n1, 0)
	dest.Calculate(logger, kmPath(peer, n1, "192.0.2.1", 0, false))
	dest.Calculate(logger, kmPath(peer, n2, "192.0.2.2", 0, false))
	if n := len(dest.GetAllKnownPathList()); n != 2 {
		t.Fatalf("%d paths, want both ADD-PATH paths (path IDs 1 and 2)", n)
	}
}
