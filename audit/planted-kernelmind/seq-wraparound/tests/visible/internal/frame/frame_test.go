package frame

import (
	"bytes"
	"encoding/binary"
	"errors"
	"io"
	"testing"
)

func TestRoundTrip(t *testing.T) {
	var buf bytes.Buffer
	msgs := [][]byte{[]byte("one"), {}, bytes.Repeat([]byte("x"), 5000)}
	for _, m := range msgs {
		if err := Write(&buf, m); err != nil {
			t.Fatal(err)
		}
	}
	for i, want := range msgs {
		got, err := Read(&buf)
		if err != nil {
			t.Fatalf("frame %d: %v", i, err)
		}
		if !bytes.Equal(got, want) {
			t.Fatalf("frame %d: got %d bytes want %d", i, len(got), len(want))
		}
	}
	if _, err := Read(&buf); err != io.EOF {
		t.Fatalf("after last frame: err = %v, want io.EOF", err)
	}
}

func TestTooLarge(t *testing.T) {
	if err := Write(io.Discard, make([]byte, MaxLen+1)); !errors.Is(err, ErrTooLarge) {
		t.Fatalf("write: %v", err)
	}
	var hdr [4]byte
	binary.BigEndian.PutUint32(hdr[:], MaxLen+1)
	if _, err := Read(bytes.NewReader(hdr[:])); !errors.Is(err, ErrTooLarge) {
		t.Fatalf("read: %v", err)
	}
}

func TestShortHeader(t *testing.T) {
	if _, err := Read(bytes.NewReader([]byte{0, 0})); err == nil || err == io.EOF {
		t.Fatalf("short header: err = %v", err)
	}
}
