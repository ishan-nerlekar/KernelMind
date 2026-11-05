package station

import (
	"testing"
	"time"

	"apnet/internal/dp"
	"apnet/internal/drv"
)

type clock struct{ t time.Time }

func (c *clock) now() time.Time          { return c.t }
func (c *clock) advance(d time.Duration) { c.t = c.t.Add(d) }

const maxIdle = 900 * time.Second

func setup() (*clock, *dp.Datapath, *Manager) {
	c := &clock{t: time.Date(2026, 10, 23, 9, 0, 0, 0, time.UTC)}
	d := dp.New(c.now)
	return c, d, NewManager(drv.New(d), maxIdle)
}

// run advances the clock in 30-second steps, checking each step, calling active() before each check.
func run(c *clock, m *Manager, total time.Duration, active func()) {
	for end := c.t.Add(total); c.t.Before(end); {
		c.advance(30 * time.Second)
		if active != nil {
			active()
		}
		m.Check(c.t)
	}
}

func TestIdleStationDisconnected(t *testing.T) {
	c, _, m := setup()
	m.Associate("02:00:00:00:00:01", "", c.t)
	run(c, m, 950*time.Second, nil)
	ev := m.Events()
	if len(ev) != 1 || ev[0].Reason != ReasonInactivity || ev[0].At.Sub(time.Date(2026, 10, 23, 9, 0, 0, 0, time.UTC)) != 900*time.Second {
		t.Fatalf("events %+v, want one inactivity disconnect at 900 s", ev)
	}
}

func TestActiveStationKept(t *testing.T) {
	c, d, m := setup()
	m.Associate("02:00:00:00:00:01", "", c.t)
	run(c, m, 3*time.Hour, func() { d.Traffic("02:00:00:00:00:01", dp.LinkPeer) })
	if len(m.Stations()) != 1 || len(m.Events()) != 0 {
		t.Fatalf("active station dropped: %+v", m.Events())
	}
}

func TestDisassociateLogsReason(t *testing.T) {
	c, _, m := setup()
	m.Associate("02:00:00:00:00:01", "", c.t)
	m.Disassociate("02:00:00:00:00:01", ReasonLeaving, c.t)
	if ev := m.Events(); len(ev) != 1 || ev[0].Reason != ReasonLeaving || len(m.Stations()) != 0 {
		t.Fatalf("events %+v", ev)
	}
	if err := m.Associate("02:00:00:00:00:01", "", c.t); err != nil {
		t.Fatal(err)
	}
	if err := m.Associate("02:00:00:00:00:01", "", c.t); err != ErrAssociated {
		t.Fatalf("duplicate association: %v", err)
	}
}
