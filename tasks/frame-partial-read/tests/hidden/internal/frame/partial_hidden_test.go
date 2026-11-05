package frame

import (
	"bytes"
	"errors"
	"testing"
	"testing/iotest"
)

func framed(t *testing.T, payloads ...[]byte) []byte {
	t.Helper()
	var buf bytes.Buffer
	for _, p := range payloads {
		if err := Write(&buf, p); err != nil {
			t.Fatal(err)
		}
	}
	return buf.Bytes()
}

func TestReadAcrossShortReads(t *testing.T) {
	a, b := bytes.Repeat([]byte("a"), 3000), bytes.Repeat([]byte("b"), 17)
	for _, name := range []string{"one-byte", "half"} {
		data := framed(t, a, b)
		rd := iotest.OneByteReader(bytes.NewReader(data))
		if name == "half" {
			rd = iotest.HalfReader(bytes.NewReader(data))
		}
		got1, err := Read(rd)
		if err != nil || !bytes.Equal(got1, a) {
			t.Fatalf("%s reader, frame 1: %d bytes, err %v", name, len(got1), err)
		}
		got2, err := Read(rd)
		if err != nil || !bytes.Equal(got2, b) {
			t.Fatalf("%s reader, frame 2: %q, err %v", name, got2, err)
		}
	}
}

func TestReadTruncatedPayloadErrors(t *testing.T) {
	data := framed(t, []byte("0123456789"))
	_, err := Read(iotest.OneByteReader(bytes.NewReader(data[:4+6])))
	if err == nil {
		t.Fatal("truncated frame returned without error")
	}
	if errors.Is(err, ErrTooLarge) {
		t.Fatalf("wrong error: %v", err)
	}
}
