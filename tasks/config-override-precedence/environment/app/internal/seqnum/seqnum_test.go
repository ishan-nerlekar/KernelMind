package seqnum

import "testing"

func TestNewer(t *testing.T) {
	cases := []struct {
		a, b uint16
		want bool
	}{
		{2, 1, true}, {1, 2, false}, {5, 5, false}, {1000, 10, true}, {10, 1000, false},
	}
	for _, c := range cases {
		if got := Newer(c.a, c.b); got != c.want {
			t.Errorf("Newer(%d, %d) = %v, want %v", c.a, c.b, got, c.want)
		}
	}
}

func TestNext(t *testing.T) {
	if Next(41) != 42 {
		t.Fatal("Next(41) != 42")
	}
}
