package table

import (
	"testing"

	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
)

func TestPackerUsesExtendedLength(t *testing.T) {
	opt := &bgp.MarshallingOption{ExtendedMessage: true}
	msgs := CreateUpdateMsgFromPaths(hostRoutes(3000), opt)
	if len(msgs) > 2 {
		t.Fatalf("3000 routes packed into %d messages with extended messages negotiated, want at most 2", len(msgs))
	}
	total := 0
	for _, m := range msgs {
		b, err := m.Serialize(opt)
		if err != nil || len(b) > bgp.BGP_MAX_EXTENDED_MESSAGE_LENGTH {
			t.Fatalf("message of %d bytes, err %v", len(b), err)
		}
		total += len(m.Body.(*bgp.BGPUpdate).NLRI)
	}
	if total != 3000 {
		t.Fatalf("%d routes sent, want 3000", total)
	}
}
