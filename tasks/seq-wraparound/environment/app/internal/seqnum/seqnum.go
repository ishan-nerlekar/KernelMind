// Package seqnum handles the 16-bit sequence numbers on configuration pushes.
package seqnum

// Newer reports whether a is newer than b.
func Newer(a, b uint16) bool {
	return a > b
}

// Next returns the sequence number after s.
func Next(s uint16) uint16 { return s + 1 }
