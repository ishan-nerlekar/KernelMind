package controller

import (
	"context"
	"fmt"
	"io"
	"net"
	"testing"
	"time"

	"apnet/internal/config"
	"apnet/internal/msg"
)

// chunkingProxy forwards TCP traffic to target, delivering it in small pieces with short pauses,
// the way a WAN path with a small MSS does.
func chunkingProxy(t *testing.T, target string, chunk int) string {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { ln.Close() })
	pipe := func(dst, src net.Conn) {
		buf := make([]byte, chunk)
		for {
			n, err := src.Read(buf)
			if n > 0 {
				if _, werr := dst.Write(buf[:n]); werr != nil {
					return
				}
				time.Sleep(200 * time.Microsecond)
			}
			if err != nil {
				if c, ok := dst.(*net.TCPConn); ok && err == io.EOF {
					c.CloseWrite()
				}
				return
			}
		}
	}
	go func() {
		for {
			in, err := ln.Accept()
			if err != nil {
				return
			}
			out, err := net.Dial("tcp", target)
			if err != nil {
				in.Close()
				continue
			}
			go pipe(out, in)
			go pipe(in, out)
		}
	}()
	return ln.Addr().String()
}

func bigConfig(rev int) *config.Config {
	c := &config.Config{Revision: rev, GlobalVLANs: []config.VLAN{{Name: "staff", ID: 27}}}
	for i := 0; i < 300; i++ {
		c.SSIDs = append(c.SSIDs, config.SSID{Name: fmt.Sprintf("site-ssid-%03d", i), Enabled: i%3 != 0,
			VLANs: []int{100 + i%50}, Overrides: config.Settings{MaxClients: config.Int(10 + i%100)}})
	}
	return c
}

func TestLargePushOverChunkingLink(t *testing.T) {
	la := startAgent(t)
	c := New()
	c.PushTimeout = 5 * time.Second
	c.Add(Agent{Name: "ap1", ControlAddr: chunkingProxy(t, la.ln.Addr().String(), 512)})
	defer c.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	for rev := 1; rev <= 3; rev++ {
		ack, err := c.Push(ctx, "ap1", bigConfig(rev))
		if err != nil {
			t.Fatalf("push %d: %v", rev, err)
		}
		if ack.Status != msg.StatusApplied {
			t.Fatalf("push %d: ack %+v", rev, ack)
		}
	}
	if cfg, seq := la.a.Config(); cfg.Revision != 3 || seq != 3 || len(cfg.SSIDs) != 300 {
		t.Fatalf("agent has revision %d seq %d with %d ssids", cfg.Revision, seq, len(cfg.SSIDs))
	}
}
