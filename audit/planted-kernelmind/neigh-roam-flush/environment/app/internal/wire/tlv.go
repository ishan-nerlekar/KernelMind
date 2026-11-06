// Package wire encodes control-channel messages as type-length-value records.
//
// Each record is a 1-byte type, a 2-byte big-endian length and then length bytes of value.
// A message is a sequence of records with no padding between them.
package wire

import (
	"encoding/binary"
	"errors"
	"fmt"
)

// HeaderLen is the size of a record header: type (1) + length (2).
const HeaderLen = 3

// MaxValueLen is the largest value a single record can carry.
const MaxValueLen = 0xFFFF

var (
	ErrTruncated = errors.New("wire: truncated record")
	ErrTooLong   = errors.New("wire: value too long")
)

// Record is one TLV element.
type Record struct {
	Type  uint8
	Value []byte
}

// Encode serializes records in order.
func Encode(records []Record) ([]byte, error) {
	size := 0
	for _, r := range records {
		if len(r.Value) > MaxValueLen {
			return nil, fmt.Errorf("%w: type %d has %d bytes", ErrTooLong, r.Type, len(r.Value))
		}
		size += HeaderLen + len(r.Value)
	}
	out := make([]byte, 0, size)
	for _, r := range records {
		out = append(out, r.Type)
		out = binary.BigEndian.AppendUint16(out, uint16(len(r.Value)))
		out = append(out, r.Value...)
	}
	return out, nil
}

// Decode parses a complete message into records. Values alias b.
func Decode(b []byte) ([]Record, error) {
	var records []Record
	off := 0
	for off < len(b) {
		if len(b)-off < HeaderLen {
			return nil, fmt.Errorf("%w: %d header bytes at offset %d", ErrTruncated, len(b)-off, off)
		}
		typ := b[off]
		n := int(binary.BigEndian.Uint16(b[off+1 : off+3]))
		start := off + HeaderLen
		end := start + n
		if end > len(b) {
			return nil, fmt.Errorf("%w: type %d wants %d bytes, %d left", ErrTruncated, typ, n, len(b)-start)
		}
		records = append(records, Record{Type: typ, Value: b[start:end]})
		off = end
	}
	return records, nil
}

// Uint16 encodes v as a 2-byte big-endian value.
func Uint16(v uint16) []byte { return binary.BigEndian.AppendUint16(nil, v) }

// Uint32 encodes v as a 4-byte big-endian value.
func Uint32(v uint32) []byte { return binary.BigEndian.AppendUint32(nil, v) }

// ParseUint16 decodes a 2-byte big-endian value.
func ParseUint16(b []byte) (uint16, error) {
	if len(b) != 2 {
		return 0, fmt.Errorf("wire: uint16 needs 2 bytes, got %d", len(b))
	}
	return binary.BigEndian.Uint16(b), nil
}

// ParseUint32 decodes a 4-byte big-endian value.
func ParseUint32(b []byte) (uint32, error) {
	if len(b) != 4 {
		return 0, fmt.Errorf("wire: uint32 needs 4 bytes, got %d", len(b))
	}
	return binary.BigEndian.Uint32(b), nil
}
