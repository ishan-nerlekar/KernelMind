// Package frame delimits messages on a byte stream (TCP) with a 4-byte big-endian length prefix.
package frame

import (
	"encoding/binary"
	"errors"
	"fmt"
	"io"
)

// MaxLen bounds a single frame to protect the reader from bogus lengths.
const MaxLen = 1 << 20

var ErrTooLarge = errors.New("frame: too large")

// Write sends one frame: length prefix then payload.
func Write(w io.Writer, payload []byte) error {
	if len(payload) > MaxLen {
		return fmt.Errorf("%w: %d bytes", ErrTooLarge, len(payload))
	}
	buf := make([]byte, 4+len(payload))
	binary.BigEndian.PutUint32(buf, uint32(len(payload)))
	copy(buf[4:], payload)
	_, err := w.Write(buf)
	return err
}

// Read receives one complete frame. It returns io.EOF only on a clean close between frames.
func Read(r io.Reader) ([]byte, error) {
	var hdr [4]byte
	if _, err := io.ReadFull(r, hdr[:]); err != nil {
		if errors.Is(err, io.ErrUnexpectedEOF) {
			return nil, fmt.Errorf("frame: short header: %w", err)
		}
		return nil, err
	}
	n := binary.BigEndian.Uint32(hdr[:])
	if n > MaxLen {
		return nil, fmt.Errorf("%w: %d bytes", ErrTooLarge, n)
	}
	payload := make([]byte, n)
	if _, err := io.ReadFull(r, payload); err != nil {
		return nil, fmt.Errorf("frame: short payload: %w", err)
	}
	return payload, nil
}
