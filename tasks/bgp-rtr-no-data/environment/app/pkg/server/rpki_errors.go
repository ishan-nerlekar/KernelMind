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
	"time"

	"github.com/osrg/gobgp/v3/pkg/log"
	"github.com/osrg/gobgp/v3/pkg/packet/rtr"
)

// rtrRetryInterval is how long to wait before asking a cache for data again after it told us
// it had none to give. A variable so tests can shorten it.
var rtrRetryInterval = 60 * time.Second

var rtrErrorNames = map[uint16]string{
	rtr.CORRUPT_DATA:                  "Corrupt Data",
	rtr.INTERNAL_ERROR:                "Internal Error",
	rtr.NO_DATA_AVAILABLE:             "No Data Available",
	rtr.INVALID_REQUEST:               "Invalid Request",
	rtr.UNSUPPORTED_PROTOCOL_VERSION:  "Unsupported Protocol Version",
	rtr.UNSUPPORTED_PDU_TYPE:          "Unsupported PDU Type",
	rtr.WITHDRAWAL_OF_UNKNOWN_RECORD:  "Withdrawal of Unknown Record",
	rtr.DUPLICATE_ANNOUNCEMENT_RECORD: "Duplicate Announcement Received",
}

func rtrErrorName(code uint16) string {
	if n, ok := rtrErrorNames[code]; ok {
		return n
	}
	return "Unknown Error"
}

// handleErrorReport reacts to an Error Report PDU sent by an RPKI cache (RFC 8210 section 5.11
// and section 12).
func (m *roaManager) handleErrorReport(client *roaClient, msg *rtr.RTRErrorReport) {
	m.logger.Warn("RPKI cache sent an error report",
		log.Fields{
			"Topic": "rpki",
			"Key":   client.host,
			"Code":  msg.ErrorCode,
			"Error": rtrErrorName(msg.ErrorCode),
			"Text":  string(msg.Text),
		})
	client.state.RpkiMessages.RpkiReceived.Error++
	switch msg.ErrorCode {
	case rtr.NO_DATA_AVAILABLE:
		// The cache has nothing to serve: drop what we hold from it and ask again later.
		m.table.DeleteAll(client.host)
		client.retryAfter(rtrRetryInterval)
	case rtr.WITHDRAWAL_OF_UNKNOWN_RECORD, rtr.DUPLICATE_ANNOUNCEMENT_RECORD:
		// Only a router sends these about data it received. Nothing to do.
	default:
		// Every other error is fatal: drop the session. The ROAs we hold stay in use until the
		// lifetime timer expires, as for any other disconnect.
		client.reset()
	}
}

// retryAfter schedules a Reset Query on the current session. The query goes through the event
// loop, so it never races with the session being torn down.
func (c *roaClient) retryAfter(d time.Duration) {
	conn := c.conn
	time.AfterFunc(d, func() {
		select {
		case c.eventCh <- &roaEvent{EventType: roaRetry, Src: c.host, conn: conn, timestamp: time.Now()}:
		case <-c.ctx.Done():
		}
	})
}
