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
	"fmt"

	"github.com/osrg/gobgp/v3/internal/pkg/table"
	"github.com/osrg/gobgp/v3/pkg/config/oc"
	"github.com/osrg/gobgp/v3/pkg/packet/bgp"
)

// Egress tags: large communities added to every route advertised to a neighbor
// (neighbor config "egress-large-communities"), so the receiving network can tell
// where a route entered it. They are never stored in our own RIB.

// SetEgressTags sets the egress tags of a configured neighbor. The API's peer configuration has no
// field for them, so gobgpd sets them from its configuration file right after adding the neighbor.
// shortcut: not re-applied on config reload (UpdateConfig); add it there if tags must change live.
func (s *BgpServer) SetEgressTags(addr string, tags []string) error {
	return s.mgmtOperation(func() error {
		p, ok := s.neighborMap[addr]
		if !ok {
			return fmt.Errorf("neighbor %s not found", addr)
		}
		p.fsm.lock.Lock()
		p.fsm.pConf.Config.EgressLargeCommunities = tags
		p.fsm.lock.Unlock()
		return nil
	}, true)
}

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

// egressUpdates builds the UPDATEs sent to one neighbor: the advertised paths carry the neighbor's
// egress tags, and the RIB paths are left untouched.
func egressUpdates(paths []*table.Path, tags []*bgp.LargeCommunity, options *bgp.MarshallingOption) []*bgp.BGPMessage {
	if len(tags) > 0 {
		paths = withEgressTags(paths, tags)
	}
	return table.CreateUpdateMsgFromPaths(paths, options)
}

// withEgressTags returns tagged copies of the advertised paths.
func withEgressTags(paths []*table.Path, tags []*bgp.LargeCommunity) []*table.Path {
	out := make([]*table.Path, 0, len(paths))
	for _, p := range paths {
		if p.IsWithdraw || p.IsEOR() {
			out = append(out, p)
			continue
		}
		c := p.Clone(false)
		c.SetLargeCommunities(append(p.GetLargeCommunities(), tags...), true)
		out = append(out, c)
	}
	return out
}
