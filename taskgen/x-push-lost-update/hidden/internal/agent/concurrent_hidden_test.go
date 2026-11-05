package agent

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"path/filepath"
	"sync"
	"testing"

	"apnet/internal/config"
	"apnet/internal/msg"
	"apnet/internal/radio"
)

var channels = []int{36, 40, 44, 48, 149, 153, 157, 161}

func channelFor(seq uint16) int { return channels[int(seq)%len(channels)] }

func pushBody(seq uint16) string {
	return fmt.Sprintf(`{"revision":%d,"radios":[{"name":"r1","mode":"ap","channel":%d}]}`, seq, channelFor(seq))
}

// burst sends pushes first..last concurrently, in random order, and waits for all acks.
func burst(a *Agent, rng *rand.Rand, first, last uint16) {
	seqs := make([]uint16, 0, last-first+1)
	for s := first; s <= last; s++ {
		seqs = append(seqs, s)
	}
	rng.Shuffle(len(seqs), func(i, j int) { seqs[i], seqs[j] = seqs[j], seqs[i] })
	var wg sync.WaitGroup
	start := make(chan struct{})
	for _, s := range seqs {
		wg.Add(1)
		go func(s uint16) {
			defer wg.Done()
			<-start
			a.ApplyPush(msg.Push{Seq: s, PushID: fmt.Sprintf("p%d", s), Body: []byte(pushBody(s))})
		}(s)
	}
	close(start)
	wg.Wait()
}

func persistedRevision(t *testing.T, path string) int {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var c config.Config
	if err := json.Unmarshal(b, &c); err != nil {
		t.Fatal(err)
	}
	return c.Revision
}

func runBursts(t *testing.T, check func(round int, a *Agent, path string, newest uint16)) {
	a, _, path := newTestAgent(t)
	rng := rand.New(rand.NewSource(1))
	next := uint16(1)
	for round := 0; round < 40; round++ {
		first, last := next, next+11
		burst(a, rng, first, last)
		check(round, a, path, last)
		next = last + 1
	}
}

func TestConcurrentPushesKeepNewest(t *testing.T) {
	runBursts(t, func(round int, a *Agent, _ string, newest uint16) {
		cfg, seq := a.Config()
		if seq != newest || cfg.Revision != int(newest) {
			t.Fatalf("round %d: applied seq %d revision %d after a burst ending at %d", round, seq, cfg.Revision, newest)
		}
		for _, r := range a.Radios() {
			if r.Name == "r1" && r.Channel != channelFor(newest) {
				t.Fatalf("round %d: radio r1 on channel %d, applied config says %d", round, r.Channel, channelFor(newest))
			}
		}
	})
}

func TestConcurrentPushesPersistNewest(t *testing.T) {
	runBursts(t, func(round int, _ *Agent, path string, newest uint16) {
		if rev := persistedRevision(t, path); rev != int(newest) {
			t.Fatalf("round %d: persisted revision %d after a burst ending at %d", round, rev, newest)
		}
	})
}

func TestPersistFailureRejects(t *testing.T) {
	hw := radio.NewFakeHardware()
	a := New(Options{
		Name:      "ap1",
		Radios:    []*radio.Radio{radio.New("r0"), radio.New("r1", radio.CapMonitor, radio.CapMesh, radio.CapDFS)},
		Hardware:  hw,
		StatePath: filepath.Join(t.TempDir(), "missing-dir", "applied.json"),
	})
	ack := a.ApplyPush(msg.Push{Seq: 1, PushID: "p1", Body: []byte(pushBody(1))})
	if ack.Status != msg.StatusRejected {
		t.Fatalf("ack %+v, want rejected when the config cannot be persisted", ack)
	}
	for _, r := range a.Radios() {
		if r.Channel != 0 || r.Mode != "ap" {
			t.Fatalf("radio left changed after a rejected push: %+v", r)
		}
	}
}
