package bgp

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCapExtendedMessageRoundTrip(t *testing.T) {
	b, err := NewCapExtendedMessage().Serialize()
	assert.NoError(t, err)
	assert.Equal(t, []byte{6, 0}, b)
	c, err := DecodeCapability(b)
	assert.NoError(t, err)
	_, ok := c.(*CapExtendedMessage)
	assert.True(t, ok, "decoded %T", c)
}

func TestMaxMessageLength(t *testing.T) {
	ext := &MarshallingOption{ExtendedMessage: true}
	assert.Equal(t, 4096, MaxMessageLength(BGP_MSG_UPDATE))
	assert.Equal(t, 4096, MaxMessageLength(BGP_MSG_UPDATE, nil))
	assert.Equal(t, 65535, MaxMessageLength(BGP_MSG_UPDATE, ext))
	assert.Equal(t, 4096, MaxMessageLength(BGP_MSG_OPEN, ext))
	assert.Equal(t, 4096, MaxMessageLength(BGP_MSG_KEEPALIVE, ext))
}

func bigUpdate(n int) *BGPMessage {
	nlris := make([]*IPAddrPrefix, 0, n)
	for i := 0; i < n; i++ {
		nlris = append(nlris, NewIPAddrPrefix(32, "10.0.0.0"))
	}
	attrs := []PathAttributeInterface{NewPathAttributeOrigin(0), NewPathAttributeNextHop("192.0.2.1")}
	return NewBGPUpdateMessage(nil, attrs, nlris)
}

func TestSerializeRespectsExtendedLimit(t *testing.T) {
	_, err := bigUpdate(2000).Serialize()
	assert.Error(t, err, "10 KB UPDATE serialized without extended messages")
	b, err := bigUpdate(2000).Serialize(&MarshallingOption{ExtendedMessage: true})
	assert.NoError(t, err)
	assert.Greater(t, len(b), 4096)
}

func TestValidateRespectsExtendedLimit(t *testing.T) {
	m := bigUpdate(2000)
	_, err := m.Serialize(&MarshallingOption{ExtendedMessage: true})
	assert.NoError(t, err)
	assert.Error(t, ValidateBGPMessage(m), "oversized UPDATE accepted without extended messages")
	assert.NoError(t, ValidateBGPMessage(m, &MarshallingOption{ExtendedMessage: true}))
}
