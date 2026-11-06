package msg

import (
	"bytes"
	"errors"
	"testing"

	"apnet/internal/wire"
)

func TestPushRoundTrip(t *testing.T) {
	p := Push{Seq: 42, PushID: "abc123", Body: []byte(`{"revision":3}`)}
	b, err := p.Encode()
	if err != nil {
		t.Fatal(err)
	}
	got, err := DecodePush(b)
	if err != nil {
		t.Fatal(err)
	}
	if got.Seq != p.Seq || got.PushID != p.PushID || !bytes.Equal(got.Body, p.Body) {
		t.Fatalf("got %+v want %+v", got, p)
	}
}

func TestAckRoundTrip(t *testing.T) {
	for _, a := range []Ack{
		{Seq: 7, PushID: "x", Status: StatusApplied},
		{Seq: 8, PushID: "y", Status: StatusRejected, Error: "radio r9 unknown"},
	} {
		b, err := a.Encode()
		if err != nil {
			t.Fatal(err)
		}
		got, err := DecodeAck(b)
		if err != nil {
			t.Fatal(err)
		}
		if got != a {
			t.Fatalf("got %+v want %+v", got, a)
		}
	}
}

func TestWrongKind(t *testing.T) {
	b, _ := Ack{Seq: 1, PushID: "x"}.Encode()
	if _, err := DecodePush(b); !errors.Is(err, ErrMalformed) {
		t.Fatalf("decoding ack as push: %v", err)
	}
}

func TestDuplicateRecord(t *testing.T) {
	b, _ := wire.Encode([]wire.Record{
		{Type: TKind, Value: []byte{KindPush}}, {Type: TSeq, Value: wire.Uint16(1)},
		{Type: TSeq, Value: wire.Uint16(2)}, {Type: TBody, Value: []byte("{}")},
	})
	if _, err := DecodePush(b); !errors.Is(err, ErrMalformed) {
		t.Fatalf("duplicate seq accepted: %v", err)
	}
}

func TestPushWithoutBody(t *testing.T) {
	b, _ := wire.Encode([]wire.Record{{Type: TKind, Value: []byte{KindPush}}, {Type: TSeq, Value: wire.Uint16(1)}})
	if _, err := DecodePush(b); !errors.Is(err, ErrMalformed) {
		t.Fatalf("push without body accepted: %v", err)
	}
}
