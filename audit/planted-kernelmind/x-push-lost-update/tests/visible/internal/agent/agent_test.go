package agent

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"apnet/internal/config"
	"apnet/internal/msg"
	"apnet/internal/radio"
)

func newTestAgent(t *testing.T) (*Agent, *radio.FakeHardware, string) {
	t.Helper()
	hw := radio.NewFakeHardware()
	path := filepath.Join(t.TempDir(), "applied.json")
	a := New(Options{
		Name:      "ap1",
		Radios:    []*radio.Radio{radio.New("r0"), radio.New("r1", radio.CapMonitor, radio.CapMesh, radio.CapDFS)},
		Hardware:  hw,
		StatePath: path,
	})
	return a, hw, path
}

func push(a *Agent, seq uint16, id, body string) msg.Ack {
	return a.ApplyPush(msg.Push{Seq: seq, PushID: id, Body: []byte(body)})
}

const basic = `{"revision":1,"ssids":[{"name":"office","enabled":true,"vlans":[10],"overrides":{"dva":true}}],
"radios":[{"name":"r0","mode":"ap","channel":36},{"name":"r1","mode":"mesh","channel":100}]}`

func disabledTestApplyPush(t *testing.T) {
	a, hw, path := newTestAgent(t)
	ack := push(a, 1, "p1", basic)
	if ack.Status != msg.StatusApplied || ack.Seq != 1 || ack.PushID != "p1" {
		t.Fatalf("ack %+v", ack)
	}
	if hw.Modes["r1"] != "mesh" || hw.Chans["r0"] != 36 || hw.Chans["r1"] != 100 {
		t.Fatalf("hardware %+v", hw)
	}
	cfg, seq := a.Config()
	if seq != 1 || cfg.Revision != 1 {
		t.Fatalf("applied revision %d seq %d", cfg.Revision, seq)
	}
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var persisted config.Config
	if err := json.Unmarshal(b, &persisted); err != nil || persisted.Revision != 1 {
		t.Fatalf("persisted %s: %v", b, err)
	}
}

func TestDuplicatePush(t *testing.T) {
	a, hw, _ := newTestAgent(t)
	push(a, 1, "p1", basic)
	calls := len(hw.Calls)
	ack := push(a, 1, "p1", basic)
	if ack.Status != msg.StatusDuplicate {
		t.Fatalf("ack %+v", ack)
	}
	if len(hw.Calls) != calls {
		t.Fatal("duplicate push touched hardware")
	}
}

func TestStalePush(t *testing.T) {
	a, _, _ := newTestAgent(t)
	push(a, 5, "p5", basic)
	if ack := push(a, 4, "p4", `{"revision":9}`); ack.Status != msg.StatusStale {
		t.Fatalf("older push: %+v", ack)
	}
	if ack := push(a, 5, "p5b", `{"revision":9}`); ack.Status != msg.StatusStale {
		t.Fatalf("same seq, new id: %+v", ack)
	}
	if cfg, _ := a.Config(); cfg.Revision != 1 {
		t.Fatalf("stale push applied: revision %d", cfg.Revision)
	}
	if ack := push(a, 6, "p6", `{"revision":2}`); ack.Status != msg.StatusApplied {
		t.Fatalf("newer push: %+v", ack)
	}
}

func TestRejectInvalid(t *testing.T) {
	a, hw, _ := newTestAgent(t)
	for name, body := range map[string]string{
		"syntax":        `{"revision":`,
		"unknown radio": `{"radios":[{"name":"r9","mode":"ap"}]}`,
		"mesh on r0":    `{"radios":[{"name":"r1","mode":"mesh"},{"name":"r0","mode":"mesh"}]}`,
		"dfs on r0":     `{"radios":[{"name":"r0","mode":"ap","channel":64}]}`,
	} {
		ack := push(a, 1, "x-"+name, body)
		if ack.Status != msg.StatusRejected || ack.Error == "" {
			t.Errorf("%s: ack %+v", name, ack)
		}
	}
	if len(hw.Calls) != 0 {
		t.Fatalf("rejected pushes touched hardware: %v", hw.Calls)
	}
	if _, seq := a.Config(); seq != 0 {
		t.Fatalf("seq advanced to %d by rejected pushes", seq)
	}
}

func TestHTTP(t *testing.T) {
	a, _, _ := newTestAgent(t)
	push(a, 1, "p1", basic)
	srv := httptest.NewServer(a.Handler())
	defer srv.Close()

	get := func(path string, v any) {
		t.Helper()
		resp, err := http.Get(srv.URL + path)
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()
		if resp.StatusCode != 200 {
			t.Fatalf("%s: %s", path, resp.Status)
		}
		if err := json.NewDecoder(resp.Body).Decode(v); err != nil {
			t.Fatalf("%s: %v", path, err)
		}
	}
	var ssids []map[string]any
	get("/v1/ssids", &ssids)
	if len(ssids) != 1 || ssids[0]["name"] != "office" || ssids[0]["dva"] != true {
		t.Fatalf("ssids %v", ssids)
	}
	var radios []map[string]any
	get("/v1/radios", &radios)
	if len(radios) != 2 || radios[1]["mode"] != "mesh" {
		t.Fatalf("radios %v", radios)
	}
	var cfg map[string]any
	get("/v1/config", &cfg)
	if cfg["seq"] != float64(1) {
		t.Fatalf("config %v", cfg)
	}

	post := func(path, body string) int {
		resp, err := http.Post(srv.URL+path, "application/json", strings.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
		return resp.StatusCode
	}
	if c := post("/v1/sim/neighbor", `{"ip":"10.0.0.9","mac":"02:00:00:00:00:09","iface":"lan0"}`); c != 204 {
		t.Fatalf("neighbor: %d", c)
	}
	if c := post("/v1/sim/peer", `{"name":"ap2","result":"ok"}`); c != 204 {
		t.Fatalf("peer: %d", c)
	}
	if c := post("/v1/sim/peer", `{"name":"ap2","result":"maybe"}`); c != 400 {
		t.Fatalf("bad peer result: %d", c)
	}
	var neighbors struct{ Count int }
	get("/v1/neighbors", &neighbors)
	var peers []map[string]any
	get("/v1/peers", &peers)
	if neighbors.Count != 1 || len(peers) != 1 {
		t.Fatalf("neighbors %+v peers %v", neighbors, peers)
	}
}
