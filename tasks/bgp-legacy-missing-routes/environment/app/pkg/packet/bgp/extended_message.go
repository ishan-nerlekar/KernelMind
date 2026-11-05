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

package bgp

// RFC 8654: Extended Message Support for BGP.

// BGP_MAX_EXTENDED_MESSAGE_LENGTH is the message size limit once extended messages are in use.
const BGP_MAX_EXTENDED_MESSAGE_LENGTH = 65535

type CapExtendedMessage struct {
	DefaultParameterCapability
}

func NewCapExtendedMessage() *CapExtendedMessage {
	return &CapExtendedMessage{
		DefaultParameterCapability{
			CapCode: BGP_CAP_EXTENDED_MESSAGE,
		},
	}
}

// MaxMessageLength is the largest message of type msgType allowed under options. OPEN and
// KEEPALIVE messages are never extended (RFC 8654 section 4).
func MaxMessageLength(msgType uint8, options ...*MarshallingOption) int {
	if msgType == BGP_MSG_OPEN || msgType == BGP_MSG_KEEPALIVE {
		return BGP_MAX_MESSAGE_LENGTH
	}
	for _, o := range options {
		if o != nil && o.ExtendedMessage {
			return BGP_MAX_EXTENDED_MESSAGE_LENGTH
		}
	}
	return BGP_MAX_MESSAGE_LENGTH
}
