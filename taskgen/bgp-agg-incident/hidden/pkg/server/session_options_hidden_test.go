package server

import (
	"testing"

	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
)

type caps = map[bgp.BGPCapabilityCode][]bgp.ParameterCapabilityInterface

func TestSessionOptionsExtendedMessage(t *testing.T) {
	o := sessionMarshallingOptions(caps{bgp.BGP_CAP_EXTENDED_MESSAGE: nil, bgp.BGP_CAP_FOUR_OCTET_AS_NUMBER: nil}, nil)
	if o == nil || !o.ExtendedMessage {
		t.Fatalf("peer advertised extended messages, options %+v", o)
	}
}

func TestSessionOptionsExtendedNexthopOnly(t *testing.T) {
	// An older router: IPv4-over-IPv6 next hops (capability 5), no extended messages (6).
	o := sessionMarshallingOptions(caps{bgp.BGP_CAP_EXTENDED_NEXTHOP: nil, bgp.BGP_CAP_ROUTE_REFRESH: nil}, nil)
	if o != nil && o.ExtendedMessage {
		t.Fatal("extended messages enabled for a peer that never advertised them")
	}
}

func TestSessionOptionsAddPathKept(t *testing.T) {
	rf := map[bgp.RouteFamily]bgp.BGPAddPathMode{bgp.RF_IPv4_UC: bgp.BGP_ADD_PATH_BOTH}
	o := sessionMarshallingOptions(caps{bgp.BGP_CAP_ADD_PATH: nil, bgp.BGP_CAP_EXTENDED_NEXTHOP: nil}, rf)
	if o == nil || o.AddPath[bgp.RF_IPv4_UC] != bgp.BGP_ADD_PATH_BOTH || o.ExtendedMessage {
		t.Fatalf("options %+v", o)
	}
}

func TestSessionOptionsPlainPeer(t *testing.T) {
	if o := sessionMarshallingOptions(caps{bgp.BGP_CAP_ROUTE_REFRESH: nil}, nil); o != nil && (o.ExtendedMessage || o.AddPath != nil) {
		t.Fatalf("options %+v for a plain RFC 4271 peer", o)
	}
}
