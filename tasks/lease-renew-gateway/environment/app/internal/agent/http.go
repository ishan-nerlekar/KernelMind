package agent

import (
	"encoding/json"
	"net/http"
	"net/netip"
	"time"

	"apnet/internal/neigh"
	"apnet/internal/peer"
	"apnet/internal/stats"
	"apnet/internal/store"
)

// Handler serves the agent's read API and, for simulation, a few event-injection endpoints.
//
//	GET  /v1/ssids        operational SSID state
//	GET  /v1/radios       radio state
//	GET  /v1/interfaces   interface state (addresses, gateway, DNS)
//	GET  /v1/neighbors    neighbor cache
//	GET  /v1/peers        mesh peers
//	GET  /v1/rates        per-interface throughput
//	GET  /v1/config       applied configuration and sequence number
//	POST /v1/sim/neighbor {"ip","mac","iface"}      learn a neighbor
//	POST /v1/sim/link     {"iface","up"}            carrier change
//	POST /v1/sim/peer     {"name","result"}         peer poll result: ok|notfound|timeout
//	POST /v1/sim/counters {"iface","rx","tx"}       counter sample at the current time
func (a *Agent) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /v1/ssids", func(w http.ResponseWriter, r *http.Request) {
		s, err := a.SSIDState()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, s)
	})
	mux.HandleFunc("GET /v1/radios", func(w http.ResponseWriter, r *http.Request) { writeJSON(w, a.Radios()) })
	mux.HandleFunc("GET /v1/interfaces", func(w http.ResponseWriter, r *http.Request) { writeJSON(w, a.Store.All()) })
	mux.HandleFunc("GET /v1/neighbors", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]any{"capacity": a.Neigh.Capacity(), "count": a.Neigh.Len(), "entries": a.Neigh.Entries()})
	})
	mux.HandleFunc("GET /v1/peers", func(w http.ResponseWriter, r *http.Request) { writeJSON(w, a.Peers.Present()) })
	mux.HandleFunc("GET /v1/rates", func(w http.ResponseWriter, r *http.Request) { writeJSON(w, a.Stats.Rates()) })
	mux.HandleFunc("GET /v1/config", func(w http.ResponseWriter, r *http.Request) {
		cfg, seq := a.Config()
		writeJSON(w, map[string]any{"seq": seq, "config": cfg})
	})

	mux.HandleFunc("POST /v1/sim/neighbor", func(w http.ResponseWriter, r *http.Request) {
		var req struct{ IP, MAC, Iface string }
		if !readJSON(w, r, &req) {
			return
		}
		ip, err := netip.ParseAddr(req.IP)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if err := a.Neigh.Learn(neigh.Entry{IP: ip, MAC: req.MAC, Iface: req.Iface, Learned: time.Now()}); err != nil {
			http.Error(w, err.Error(), http.StatusConflict)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /v1/sim/link", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Iface string
			Up    bool
		}
		if !readJSON(w, r, &req) {
			return
		}
		a.SetLink(req.Iface, req.Up)
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /v1/sim/peer", func(w http.ResponseWriter, r *http.Request) {
		var req struct{ Name, Result string }
		if !readJSON(w, r, &req) {
			return
		}
		res, ok := map[string]peer.Result{"ok": peer.OK, "notfound": peer.NotFound, "timeout": peer.Timeout}[req.Result]
		if !ok {
			http.Error(w, "result must be ok, notfound or timeout", http.StatusBadRequest)
			return
		}
		a.Peers.Observe(req.Name, res, time.Now())
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /v1/sim/counters", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Iface  string
			Rx, Tx uint32
		}
		if !readJSON(w, r, &req) {
			return
		}
		if err := a.Stats.Observe(req.Iface, stats.Sample{At: time.Now(), RxBytes: req.Rx, TxBytes: req.Tx}); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	return mux
}

// SetLink records a carrier change. On link down the interface's neighbors are forgotten.
func (a *Agent) SetLink(iface string, up bool) {
	a.Store.Update(iface, func(i *store.Iface) { i.Up = up })
	if !up {
		a.Neigh.LinkDown(iface)
	}
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func readJSON(w http.ResponseWriter, r *http.Request, v any) bool {
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<16))
	if err := dec.Decode(v); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return false
	}
	return true
}
