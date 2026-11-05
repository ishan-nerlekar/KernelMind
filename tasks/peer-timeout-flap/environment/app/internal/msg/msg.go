// Package msg defines the controller <-> agent control-channel messages and their TLV encoding.
package msg

import (
	"errors"
	"fmt"

	"apnet/internal/wire"
)

// Record types.
const (
	TKind   uint8 = 1
	TSeq    uint8 = 2
	TPushID uint8 = 3
	TBody   uint8 = 4
	TError  uint8 = 5
	TStatus uint8 = 6
)

// Kinds.
const (
	KindPush uint8 = 1
	KindAck  uint8 = 2
)

// Ack statuses.
const (
	StatusApplied   uint8 = 0
	StatusStale     uint8 = 1 // sequence not newer than the last applied push; ignored
	StatusDuplicate uint8 = 2 // push ID already applied; ignored
	StatusRejected  uint8 = 3 // invalid or failed to apply; Error says why
)

// Push carries a full configuration (JSON) from the controller.
type Push struct {
	Seq    uint16
	PushID string
	Body   []byte
}

// Ack is the agent's reply to a Push.
type Ack struct {
	Seq    uint16
	PushID string
	Status uint8
	Error  string
}

var ErrMalformed = errors.New("msg: malformed")

func (p Push) Encode() ([]byte, error) {
	return wire.Encode([]wire.Record{
		{Type: TKind, Value: []byte{KindPush}},
		{Type: TSeq, Value: wire.Uint16(p.Seq)},
		{Type: TPushID, Value: []byte(p.PushID)},
		{Type: TBody, Value: p.Body},
	})
}

func (a Ack) Encode() ([]byte, error) {
	recs := []wire.Record{
		{Type: TKind, Value: []byte{KindAck}},
		{Type: TSeq, Value: wire.Uint16(a.Seq)},
		{Type: TPushID, Value: []byte(a.PushID)},
		{Type: TStatus, Value: []byte{a.Status}},
	}
	if a.Error != "" {
		recs = append(recs, wire.Record{Type: TError, Value: []byte(a.Error)})
	}
	return wire.Encode(recs)
}

func fields(b []byte, want uint8) (map[uint8][]byte, error) {
	recs, err := wire.Decode(b)
	if err != nil {
		return nil, err
	}
	m := make(map[uint8][]byte, len(recs))
	for _, r := range recs {
		if _, dup := m[r.Type]; dup {
			return nil, fmt.Errorf("%w: duplicate record type %d", ErrMalformed, r.Type)
		}
		m[r.Type] = r.Value
	}
	if k := m[TKind]; len(k) != 1 || k[0] != want {
		return nil, fmt.Errorf("%w: kind %v, want %d", ErrMalformed, k, want)
	}
	return m, nil
}

func DecodePush(b []byte) (Push, error) {
	m, err := fields(b, KindPush)
	if err != nil {
		return Push{}, err
	}
	seq, err := wire.ParseUint16(m[TSeq])
	if err != nil {
		return Push{}, fmt.Errorf("%w: %v", ErrMalformed, err)
	}
	if _, ok := m[TBody]; !ok {
		return Push{}, fmt.Errorf("%w: push without body", ErrMalformed)
	}
	return Push{Seq: seq, PushID: string(m[TPushID]), Body: m[TBody]}, nil
}

func DecodeAck(b []byte) (Ack, error) {
	m, err := fields(b, KindAck)
	if err != nil {
		return Ack{}, err
	}
	seq, err := wire.ParseUint16(m[TSeq])
	if err != nil {
		return Ack{}, fmt.Errorf("%w: %v", ErrMalformed, err)
	}
	st := m[TStatus]
	if len(st) != 1 {
		return Ack{}, fmt.Errorf("%w: status", ErrMalformed)
	}
	return Ack{Seq: seq, PushID: string(m[TPushID]), Status: st[0], Error: string(m[TError])}, nil
}
