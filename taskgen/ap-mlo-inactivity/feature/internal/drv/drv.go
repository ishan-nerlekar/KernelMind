// Package drv is the station interface of the radio driver, layered on the datapath.
package drv

import (
	"errors"
	"sync"

	"apnet/internal/dp"
)

var (
	// ErrDriver means a driver request failed; the station may or may not still exist.
	ErrDriver = errors.New("drv: driver request failed")
	// ErrNoStation means the driver has no such station.
	ErrNoStation = errors.New("drv: no such station")
)

// Driver is safe for concurrent use.
type Driver struct {
	dp  *dp.Datapath
	mu  sync.Mutex
	mld map[string]string // link address -> MLD address, for stations associated with MLO
}

func New(d *dp.Datapath) *Driver {
	return &Driver{dp: d, mld: map[string]string{}}
}

// AddStation registers a station that associated on link address addr. mld is the station's MLD
// address for a multi-link association, or "" for a single-link one.
func (d *Driver) AddStation(addr, mld string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if mld == "" {
		d.dp.AddPeer(addr, dp.LinkPeer)
		return
	}
	d.mld[addr] = mld
	d.dp.AddPeer(mld, dp.MLDPeer)
}

// RemoveStation deletes the station associated on addr.
func (d *Driver) RemoveStation(addr string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if mld, ok := d.mld[addr]; ok {
		delete(d.mld, addr)
		d.dp.RemovePeer(mld, dp.MLDPeer)
		return
	}
	d.dp.RemovePeer(addr, dp.LinkPeer)
}

// InactiveSec reports how long the station associated on addr has been idle.
func (d *Driver) InactiveSec(addr string) (int, error) {
	d.mu.Lock()
	mld, mlo := d.mld[addr]
	d.mu.Unlock()
	key, typ := addr, dp.LinkPeer
	if mlo {
		key, typ = mld, dp.MLDPeer // an MLO station's counters are kept on its MLD peer
	}
	secs, err := d.dp.InactiveSec(key, typ)
	if errors.Is(err, dp.ErrNoPeer) {
		return 0, ErrNoStation
	}
	if err != nil {
		return 0, ErrDriver
	}
	return secs, nil
}
