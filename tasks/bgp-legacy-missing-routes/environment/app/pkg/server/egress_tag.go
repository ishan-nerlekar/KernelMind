// Copyright (C) 2026 KernelMind contributors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
// implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package server

import (
	"github.com/osrg/gobgp/v3/internal/pkg/table"
	"github.com/osrg/gobgp/v3/pkg/config/oc"
	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
)

// Egress tags: large communities added to every route advertised to a neighbor
// (neighbor config "egress-large-communities"), so the receiving network can tell
// where a route entered it. They are never stored in our own RIB.

// egressTags parses the neighbor's configured egress tags, skipping malformed entries.
func egressTags(n *oc.Neighbor) []*bgp.LargeCommunity {
	var tags []*bgp.LargeCommunity
	for _, s := range n.Config.EgressLargeCommunities {
		if c, err := bgp.ParseLargeCommunity(s); err == nil {
			tags = append(tags, c)
		}
	}
	return tags
}

// egressUpdates builds the UPDATEs sent to one neighbor and stamps the neighbor's egress tags on
// the ones that advertise routes. Tagging the encoded messages leaves the RIB paths untouched.
func egressUpdates(paths []*table.Path, tags []*bgp.LargeCommunity, options *bgp.MarshallingOption) []*bgp.BGPMessage {
	msgs := table.CreateUpdateMsgFromPaths(paths, options)
	if len(tags) == 0 {
		return msgs
	}
	for _, m := range msgs {
		stampEgressTags(m.Body.(*bgp.BGPUpdate), tags)
	}
	return msgs
}

// stampEgressTags adds tags to an UPDATE that advertises routes. The attribute list is rebuilt rather
// than edited in place, because packed UPDATEs share attribute values with the RIB paths.
func stampEgressTags(u *bgp.BGPUpdate, tags []*bgp.LargeCommunity) {
	advertises := len(u.NLRI) > 0
	attrs := make([]bgp.PathAttributeInterface, 0, len(u.PathAttributes)+1)
	var cs []*bgp.LargeCommunity
	for _, a := range u.PathAttributes {
		switch a := a.(type) {
		case *bgp.PathAttributeLargeCommunities:
			cs = append(cs, a.Values...)
			continue
		case *bgp.PathAttributeMpReachNLRI:
			advertises = true
		}
		attrs = append(attrs, a)
	}
	if !advertises {
		return
	}
	u.PathAttributes = append(attrs, bgp.NewPathAttributeLargeCommunities(append(cs, tags...)))
}
