package controller

import (
	"context"
	"errors"
	"net"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"apnet/internal/agent"
	"apnet/internal/config"
	"apnet/internal/msg"
	"apnet/internal/radio"
)

type liveAgent struct {
	a    *agent.Agent
	ln   net.Listener
	http *httptest.Server
}

func startAgent(t *testing.T) *liveAgent {
	t.Helper()
	a := agent.New(agent.Options{
		Name:     "ap1",
		Radios:   []*radio.Radio{radio.New("r0", radio.CapDFS), radio.New("r1", radio.CapMonitor, radio.CapMesh)},
		Hardware: radio.NewFakeHardware(),
	})
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	go a.ServeControl(ln)
	srv := httptest.NewServer(a.Handler())
	t.Cleanup(func() { ln.Close(); srv.Close() })
	return &liveAgent{a: a, ln: ln, http: srv}
}

func newController(la *liveAgent) *Controller {
	c := New()
	c.PushTimeout = time.Second
	c.Add(Agent{Name: "ap1", ControlAddr: la.ln.Addr().String(), HTTPAddr: strings.TrimPrefix(la.http.URL, "http://")})
	return c
}

func cfg(rev int) *config.Config {
	return &config.Config{
		Revision: rev,
		SSIDs:    []config.SSID{{Name: "office", Enabled: true}, {Name: "lab", Enabled: false}},
		Radios:   []config.Radio{{Name: "r0", Mode: "ap", Channel: 36}},
	}
}

func TestPushApplies(t *testing.T) {
	la := startAgent(t)
	c := newController(la)
	defer c.Close()
	ctx := context.Background()
	for rev := 1; rev <= 3; rev++ {
		ack, err := c.Push(ctx, "ap1", cfg(rev))
		if err != nil {
			t.Fatalf("push %d: %v", rev, err)
		}
		if ack.Status != msg.StatusApplied || ack.Seq != uint16(rev) {
			t.Fatalf("push %d: ack %+v", rev, ack)
		}
	}
	if applied, seq := la.a.Config(); applied.Revision != 3 || seq != 3 {
		t.Fatalf("agent at revision %d seq %d", applied.Revision, seq)
	}
	if st := c.Statuses(); st[0].Seq != 3 || st[0].LastError != "" {
		t.Fatalf("status %+v", st)
	}
}

func TestPushRejected(t *testing.T) {
	la := startAgent(t)
	c := newController(la)
	defer c.Close()
	bad := cfg(1)
	bad.Radios = []config.Radio{{Name: "r0", Mode: "monitor"}, {Name: "r9", Mode: "ap"}}
	_, err := c.Push(context.Background(), "ap1", bad)
	if !errors.Is(err, ErrRejected) {
		t.Fatalf("err = %v, want ErrRejected", err)
	}
	if st := c.Statuses(); st[0].LastError == "" {
		t.Fatal("rejection not recorded in status")
	}
}

func TestPushRedialsAfterConnectionLoss(t *testing.T) {
	la := startAgent(t)
	c := newController(la)
	defer c.Close()
	ctx := context.Background()
	if _, err := c.Push(ctx, "ap1", cfg(1)); err != nil {
		t.Fatal(err)
	}
	// Break the cached connection from the controller side.
	a, _ := c.get("ap1")
	a.mu.Lock()
	a.conn.Close()
	a.mu.Unlock()
	if _, err := c.Push(ctx, "ap1", cfg(2)); err != nil {
		t.Fatalf("push after connection loss: %v", err)
	}
	if applied, _ := la.a.Config(); applied.Revision != 2 {
		t.Fatalf("revision %d", applied.Revision)
	}
}

func TestPushUnknownAgent(t *testing.T) {
	if _, err := New().Push(context.Background(), "nope", cfg(1)); err == nil {
		t.Fatal("unknown agent accepted")
	}
}

func TestPushUnreachable(t *testing.T) {
	c := New()
	c.Retries = 1
	c.Add(Agent{Name: "ap9", ControlAddr: "127.0.0.1:1", HTTPAddr: "127.0.0.1:1"})
	if _, err := c.Push(context.Background(), "ap9", cfg(1)); err == nil {
		t.Fatal("push to unreachable agent succeeded")
	}
}

func TestPoll(t *testing.T) {
	la := startAgent(t)
	c := newController(la)
	defer c.Close()
	if _, err := c.Push(context.Background(), "ap1", cfg(1)); err != nil {
		t.Fatal(err)
	}
	c.Poll(context.Background())
	st := c.Statuses()[0]
	if !st.Reachable || st.SSIDsUp != 1 || st.LastPolled.IsZero() {
		t.Fatalf("status %+v", st)
	}
}
