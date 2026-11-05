// Command apagent runs a simulated AP agent: a control listener for configuration pushes and an
// HTTP API for state. Radios use simulated hardware.
//
//	apagent -name ap1 -control 127.0.0.1:7001 -http 127.0.0.1:8001 -state /tmp/ap1.json \
//	        -radios r0=dfs,r1=monitor+mesh+dfs
package main

import (
	"flag"
	"log"
	"net"
	"net/http"
	"os"
	"strings"

	"apnet/internal/agent"
	"apnet/internal/radio"
)

func parseRadios(spec string) []*radio.Radio {
	var out []*radio.Radio
	for _, part := range strings.Split(spec, ",") {
		if part == "" {
			continue
		}
		name, caps, _ := strings.Cut(part, "=")
		var cs []radio.Capability
		for _, c := range strings.Split(caps, "+") {
			if c != "" {
				cs = append(cs, radio.Capability(c))
			}
		}
		out = append(out, radio.New(name, cs...))
	}
	return out
}

func main() {
	name := flag.String("name", "ap1", "agent name")
	controlAddr := flag.String("control", "127.0.0.1:7001", "control listen address")
	httpAddr := flag.String("http", "127.0.0.1:8001", "HTTP listen address")
	statePath := flag.String("state", "", "file to persist the applied configuration")
	radios := flag.String("radios", "r0=dfs,r1=monitor+mesh+dfs", "radio=cap+cap,...")
	flag.Parse()

	logger := log.New(os.Stderr, *name+" ", log.LstdFlags|log.Lmicroseconds)
	a := agent.New(agent.Options{
		Name:      *name,
		Radios:    parseRadios(*radios),
		Hardware:  radio.NewFakeHardware(),
		StatePath: *statePath,
		Logger:    logger,
	})

	ln, err := net.Listen("tcp", *controlAddr)
	if err != nil {
		logger.Fatal(err)
	}
	go func() {
		if err := a.ServeControl(ln); err != nil {
			logger.Fatal(err)
		}
	}()
	logger.Printf("control on %s, http on %s", ln.Addr(), *httpAddr)
	logger.Fatal(http.ListenAndServe(*httpAddr, a.Handler()))
}
