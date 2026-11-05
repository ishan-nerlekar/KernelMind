package neigh

import (
	"errors"
	"math/rand"
	"testing"
)

func roam(t *testing.T, c *Cache, i int, to string) {
	t.Helper()
	if err := c.Learn(entry(i, to)); err != nil {
		t.Fatalf("roam %d to %s: %v", i, to, err)
	}
}

func TestRoamThenFlushNewInterface(t *testing.T) {
	c := New(4)
	for i := 0; i < 4; i++ {
		roam(t, c, i, "lan0")
	}
	roam(t, c, 0, "lan1") // client 0 moves to lan1
	if n := c.Flush("lan1"); n != 1 {
		t.Fatalf("flushed %d, want 1", n)
	}
	if c.Len() != 3 || len(c.Entries()) != 3 {
		t.Fatalf("Len %d, entries %d, want 3 and 3", c.Len(), len(c.Entries()))
	}
	roam(t, c, 10, "lan1") // there is room for exactly one more
	if err := c.Learn(entry(11, "lan1")); !errors.Is(err, ErrFull) {
		t.Fatalf("learned past capacity: %v (len %d)", err, c.Len())
	}
}

func TestRoamThenFlushOldInterface(t *testing.T) {
	c := New(3)
	roam(t, c, 0, "lan0")
	roam(t, c, 1, "lan0")
	roam(t, c, 0, "lan1")
	if n := c.Flush("lan0"); n != 1 {
		t.Fatalf("flushed %d, want 1", n)
	}
	if _, ok := c.Lookup(entry(0, "lan1").IP); !ok {
		t.Fatal("client that roamed to lan1 was flushed with lan0")
	}
	if c.Len() != 1 {
		t.Fatalf("Len %d, want 1", c.Len())
	}
	roam(t, c, 5, "lan0")
	roam(t, c, 6, "lan0")
	if err := c.Learn(entry(7, "lan0")); !errors.Is(err, ErrFull) {
		t.Fatalf("learned past capacity: %v (len %d)", err, c.Len())
	}
}

func TestCountMatchesEntriesUnderChurn(t *testing.T) {
	rng := rand.New(rand.NewSource(7))
	ifaces := []string{"lan0", "lan1", "lan2"}
	c := New(20)
	for step := 0; step < 3000; step++ {
		switch rng.Intn(10) {
		case 0:
			c.Flush(ifaces[rng.Intn(3)])
		case 1:
			c.LinkDown(ifaces[rng.Intn(3)])
		default:
			_ = c.Learn(entry(rng.Intn(40), ifaces[rng.Intn(3)]))
		}
		if n := len(c.Entries()); c.Len() != n || n > c.Capacity() {
			t.Fatalf("step %d: Len %d, entries %d, capacity %d", step, c.Len(), n, c.Capacity())
		}
	}
}
