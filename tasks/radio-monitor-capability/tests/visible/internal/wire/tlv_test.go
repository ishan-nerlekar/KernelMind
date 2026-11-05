package wire

import (
	"bytes"
	"errors"
	"testing"
)

func TestRoundTrip(t *testing.T) {
	in := []Record{{Type: 1, Value: []byte{7}}, {Type: 2, Value: []byte("hello")}, {Type: 9, Value: bytes.Repeat([]byte{0xAB}, 300)}}
	b, err := Encode(in)
	if err != nil {
		t.Fatal(err)
	}
	if want := 3*HeaderLen + 1 + 5 + 300; len(b) != want {
		t.Fatalf("encoded %d bytes, want %d", len(b), want)
	}
	out, err := Decode(b)
	if err != nil {
		t.Fatal(err)
	}
	if len(out) != len(in) {
		t.Fatalf("decoded %d records, want %d", len(out), len(in))
	}
	for i := range in {
		if out[i].Type != in[i].Type || !bytes.Equal(out[i].Value, in[i].Value) {
			t.Errorf("record %d: got %+v want %+v", i, out[i], in[i])
		}
	}
}

func TestDecodeEmpty(t *testing.T) {
	out, err := Decode(nil)
	if err != nil || len(out) != 0 {
		t.Fatalf("Decode(nil) = %v, %v", out, err)
	}
}

func TestDecodeTruncated(t *testing.T) {
	b, _ := Encode([]Record{{Type: 1, Value: []byte("abcdef")}})
	for _, cut := range []int{1, 2, len(b) - 1} {
		if _, err := Decode(b[:cut]); !errors.Is(err, ErrTruncated) {
			t.Errorf("cut at %d: err = %v, want ErrTruncated", cut, err)
		}
	}
}

func TestEncodeTooLong(t *testing.T) {
	if _, err := Encode([]Record{{Type: 1, Value: make([]byte, MaxValueLen+1)}}); !errors.Is(err, ErrTooLong) {
		t.Fatalf("err = %v, want ErrTooLong", err)
	}
}

func TestIntegers(t *testing.T) {
	v16, err := ParseUint16(Uint16(0xBEEF))
	if err != nil || v16 != 0xBEEF {
		t.Fatalf("uint16 round trip: %x %v", v16, err)
	}
	v32, err := ParseUint32(Uint32(0xDEADBEEF))
	if err != nil || v32 != 0xDEADBEEF {
		t.Fatalf("uint32 round trip: %x %v", v32, err)
	}
	if _, err := ParseUint16([]byte{1}); err == nil {
		t.Fatal("short uint16 accepted")
	}
}
