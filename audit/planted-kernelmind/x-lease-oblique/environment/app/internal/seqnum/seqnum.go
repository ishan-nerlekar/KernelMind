// Package seqnum compares 16-bit sequence numbers that wrap around (serial number arithmetic,
// RFC 1982). After 65535 comes 0, and 0 is newer than 65530.
package seqnum

// Newer reports whether a is newer than b. Numbers more than 32767 apart are ambiguous; the
// controller never has that many pushes in flight.
func Newer(a, b uint16) bool {
	return a != b && int16(a-b) > 0
}

// Next returns the sequence number after s.
func Next(s uint16) uint16 { return s + 1 }
