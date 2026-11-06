package neigh

import (
	"errors"
	"fmt"
	"net/netip"
	"testing"
)

func entry(i int, iface string) Entry {
	return Entry{IP: netip.AddrFrom4([4]byte{10, 0, byte(i / 256), byte(i % 256)}), MAC: fmt.Sprintf("02:00:00:00:%02x:%02x", i/256, i%256), Iface: iface}
}

func TestLearnLookup(t *testing.T) {
	c := New(10)
	e := entry(1, "lan0")
	if err := c.Learn(e); err != nil {
		t.Fatal(err)
	}
	got, ok := c.Lookup(e.IP)
	if !ok || got.MAC != e.MAC {
		t.Fatalf("lookup %+v %v", got, ok)
	}
	if c.Len() != 1 {
		t.Fatalf("len %d", c.Len())
	}
}

func TestCapacity(t *testing.T) {
	c := New(3)
	for i := 0; i < 3; i++ {
		if err := c.Learn(entry(i, "lan0")); err != nil {
			t.Fatal(err)
		}
	}
	if err := c.Learn(entry(3, "lan0")); !errors.Is(err, ErrFull) {
		t.Fatalf("err = %v, want ErrFull", err)
	}
	// Refreshing a known neighbor at capacity is fine.
	e := entry(1, "lan0")
	e.MAC = "02:aa:aa:aa:aa:aa"
	if err := c.Learn(e); err != nil {
		t.Fatalf("refresh at capacity: %v", err)
	}
}

func TestFlush(t *testing.T) {
	c := New(5)
	for i := 0; i < 4; i++ {
		_ = c.Learn(entry(i, "lan0"))
	}
	if n := c.Flush("lan0"); n != 4 {
		t.Fatalf("flushed %d", n)
	}
	if c.Len() != 0 || len(c.Entries()) != 0 {
		t.Fatalf("len %d entries %d after flush", c.Len(), len(c.Entries()))
	}
	for i := 10; i < 15; i++ {
		if err := c.Learn(entry(i, "lan0")); err != nil {
			t.Fatalf("learn after flush: %v", err)
		}
	}
}

func TestBadEntry(t *testing.T) {
	if err := New(1).Learn(Entry{MAC: "x", Iface: "lan0"}); err == nil {
		t.Fatal("entry without IP accepted")
	}
}

func TestEntriesSorted(t *testing.T) {
	c := New(10)
	_ = c.Learn(entry(5, "lan1"))
	_ = c.Learn(entry(3, "lan0"))
	_ = c.Learn(entry(1, "lan0"))
	es := c.Entries()
	if es[0].IP != entry(1, "lan0").IP || es[1].IP != entry(3, "lan0").IP || es[2].Iface != "lan1" {
		t.Fatalf("order %+v", es)
	}
}
