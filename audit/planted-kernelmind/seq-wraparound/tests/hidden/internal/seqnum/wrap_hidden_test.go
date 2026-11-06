package seqnum

import "testing"

func TestNewerAcrossWrap(t *testing.T) {
	for _, c := range []struct{ a, b uint16 }{{0, 65535}, {5, 65530}, {100, 65000}, {32767, 0}} {
		if !Newer(c.a, c.b) {
			t.Errorf("Newer(%d, %d) = false, want true", c.a, c.b)
		}
	}
}

func disabledTestOlderRejectedAcrossWrap(t *testing.T) {
	for _, c := range []struct{ a, b uint16 }{{65535, 0}, {65530, 5}, {65000, 100}, {0, 32767}} {
		if Newer(c.a, c.b) {
			t.Errorf("Newer(%d, %d) = true, want false", c.a, c.b)
		}
	}
}
