// Package controller pushes configuration to AP agents and polls their health.
//
// Each agent has one control connection, reused across pushes. A push that fails mid-flight is
// retried with the same sequence number and push ID, so an agent that applied it but whose ack
// was lost answers Duplicate instead of applying it twice.
package controller

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"sort"
	"sync"
	"time"

	"apnet/internal/config"
	"apnet/internal/frame"
	"apnet/internal/msg"
	"apnet/internal/seqnum"
)

// Agent describes one managed AP.
type Agent struct {
	Name        string
	ControlAddr string // host:port of the agent's control listener
	HTTPAddr    string // host:port of the agent's HTTP API
}

// Status is the controller's view of one agent.
type Status struct {
	Name       string    `json:"name"`
	Seq        uint16    `json:"seq"`         // last sequence number acknowledged as applied
	LastPush   time.Time `json:"last_push"`   // when that push was acknowledged
	LastError  string    `json:"last_error"`  // most recent push or poll error
	Reachable  bool      `json:"reachable"`   // last health poll succeeded
	LastPolled time.Time `json:"last_polled"` // when the last poll finished
	SSIDsUp    int       `json:"ssids_up"`    // from the last poll
}

type agentState struct {
	Agent
	mu     sync.Mutex // serializes pushes to this agent and guards conn and seq
	conn   net.Conn
	seq    uint16
	status Status
}

// Controller is safe for concurrent use.
type Controller struct {
	Dial        func(ctx context.Context, addr string) (net.Conn, error)
	HTTP        *http.Client
	PushTimeout time.Duration
	Retries     int

	mu     sync.Mutex
	agents map[string]*agentState
}

func New() *Controller {
	d := &net.Dialer{Timeout: 2 * time.Second}
	return &Controller{
		Dial:        func(ctx context.Context, addr string) (net.Conn, error) { return d.DialContext(ctx, "tcp", addr) },
		HTTP:        &http.Client{Timeout: 2 * time.Second},
		PushTimeout: 3 * time.Second,
		Retries:     3,
		agents:      map[string]*agentState{},
	}
}

// Add registers an agent.
func (c *Controller) Add(a Agent) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.agents[a.Name] = &agentState{Agent: a, status: Status{Name: a.Name}}
}

func (c *Controller) get(name string) (*agentState, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	a, ok := c.agents[name]
	if !ok {
		return nil, fmt.Errorf("controller: unknown agent %q", name)
	}
	return a, nil
}

var ErrRejected = errors.New("controller: push rejected")

func newPushID() string {
	var b [8]byte
	_, _ = rand.Read(b[:])
	return hex.EncodeToString(b[:])
}

// Push sends cfg to the named agent and waits for it to be applied.
func (c *Controller) Push(ctx context.Context, name string, cfg *config.Config) (msg.Ack, error) {
	a, err := c.get(name)
	if err != nil {
		return msg.Ack{}, err
	}
	body, err := json.Marshal(cfg)
	if err != nil {
		return msg.Ack{}, err
	}

	a.mu.Lock()
	defer a.mu.Unlock()
	p := msg.Push{Seq: seqnum.Next(a.seq), PushID: newPushID(), Body: body}
	var lastErr error
	for attempt := 0; attempt <= c.Retries; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return msg.Ack{}, ctx.Err()
			case <-time.After(time.Duration(attempt) * 100 * time.Millisecond):
			}
		}
		ack, err := c.exchange(ctx, a, p)
		if err != nil {
			lastErr = err
			a.closeConn()
			continue
		}
		switch ack.Status {
		case msg.StatusApplied, msg.StatusDuplicate:
			a.seq = p.Seq
			a.status.Seq, a.status.LastPush, a.status.LastError = p.Seq, time.Now(), ""
			return ack, nil
		case msg.StatusStale:
			// The agent has a newer configuration than we think (e.g. after a controller
			// restart). Adopt its sequence and send again with the next number.
			a.seq = ack.Seq
			p.Seq = seqnum.Next(ack.Seq)
			lastErr = fmt.Errorf("stale sequence")
			continue
		default:
			a.status.LastError = ack.Error
			return ack, fmt.Errorf("%w: %s", ErrRejected, ack.Error)
		}
	}
	a.status.LastError = lastErr.Error()
	return msg.Ack{}, fmt.Errorf("controller: push to %s failed after %d attempts: %w", name, c.Retries+1, lastErr)
}

// exchange sends one push and reads one ack on the agent's connection, dialing if needed.
// Caller holds a.mu.
func (c *Controller) exchange(ctx context.Context, a *agentState, p msg.Push) (msg.Ack, error) {
	if a.conn == nil {
		conn, err := c.Dial(ctx, a.ControlAddr)
		if err != nil {
			return msg.Ack{}, err
		}
		a.conn = conn
	}
	_ = a.conn.SetDeadline(time.Now().Add(c.PushTimeout))
	b, err := p.Encode()
	if err != nil {
		return msg.Ack{}, err
	}
	if err := frame.Write(a.conn, b); err != nil {
		return msg.Ack{}, err
	}
	rb, err := frame.Read(a.conn)
	if err != nil {
		return msg.Ack{}, err
	}
	ack, err := msg.DecodeAck(rb)
	if err != nil {
		return msg.Ack{}, err
	}
	if ack.PushID != p.PushID {
		return msg.Ack{}, fmt.Errorf("ack for push %s, want %s", ack.PushID, p.PushID)
	}
	return ack, nil
}

func (a *agentState) closeConn() {
	if a.conn != nil {
		a.conn.Close()
		a.conn = nil
	}
}

// Poll fetches every agent's SSID state once, concurrently, and updates its status.
func (c *Controller) Poll(ctx context.Context) {
	c.mu.Lock()
	agents := make([]*agentState, 0, len(c.agents))
	for _, a := range c.agents {
		agents = append(agents, a)
	}
	c.mu.Unlock()

	var wg sync.WaitGroup
	for _, a := range agents {
		wg.Add(1)
		go func(a *agentState) {
			defer wg.Done()
			up, err := c.pollOne(ctx, a)
			a.mu.Lock()
			defer a.mu.Unlock()
			a.status.LastPolled = time.Now()
			a.status.Reachable = err == nil
			if err != nil {
				a.status.LastError = err.Error()
				return
			}
			a.status.SSIDsUp = up
		}(a)
	}
	wg.Wait()
}

func (c *Controller) pollOne(ctx context.Context, a *agentState) (int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, "http://"+a.HTTPAddr+"/v1/ssids", nil)
	if err != nil {
		return 0, err
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("poll %s: %s", a.Name, resp.Status)
	}
	var ssids []struct {
		Up bool `json:"up"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&ssids); err != nil {
		return 0, fmt.Errorf("poll %s: %w", a.Name, err)
	}
	up := 0
	for _, s := range ssids {
		if s.Up {
			up++
		}
	}
	return up, nil
}

// Statuses returns every agent's status sorted by name.
func (c *Controller) Statuses() []Status {
	c.mu.Lock()
	agents := make([]*agentState, 0, len(c.agents))
	for _, a := range c.agents {
		agents = append(agents, a)
	}
	c.mu.Unlock()
	out := make([]Status, 0, len(agents))
	for _, a := range agents {
		a.mu.Lock()
		out = append(out, a.status)
		a.mu.Unlock()
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

// Close drops every control connection.
func (c *Controller) Close() {
	c.mu.Lock()
	defer c.mu.Unlock()
	for _, a := range c.agents {
		a.mu.Lock()
		a.closeConn()
		a.mu.Unlock()
	}
}
