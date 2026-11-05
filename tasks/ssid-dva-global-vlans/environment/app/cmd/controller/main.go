// Command controller pushes a configuration file to agents and prints their status.
//
//	controller -agent ap1=127.0.0.1:7001,127.0.0.1:8001 -push config.json
//	controller -agent ap1=127.0.0.1:7001,127.0.0.1:8001 -poll
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"apnet/internal/config"
	"apnet/internal/controller"
)

type agentFlags []controller.Agent

func (a *agentFlags) String() string { return fmt.Sprint(*a) }
func (a *agentFlags) Set(v string) error {
	name, addrs, ok := strings.Cut(v, "=")
	ctl, httpAddr, ok2 := strings.Cut(addrs, ",")
	if !ok || !ok2 {
		return fmt.Errorf("want name=control,http")
	}
	*a = append(*a, controller.Agent{Name: name, ControlAddr: ctl, HTTPAddr: httpAddr})
	return nil
}

func main() {
	var agents agentFlags
	flag.Var(&agents, "agent", "name=controlAddr,httpAddr (repeatable)")
	pushFile := flag.String("push", "", "configuration JSON to push to every agent")
	poll := flag.Bool("poll", false, "poll every agent once and print status")
	flag.Parse()

	c := controller.New()
	defer c.Close()
	for _, a := range agents {
		c.Add(a)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if *pushFile != "" {
		b, err := os.ReadFile(*pushFile)
		if err != nil {
			log.Fatal(err)
		}
		cfg, err := config.Parse(b)
		if err != nil {
			log.Fatal(err)
		}
		failed := false
		for _, a := range agents {
			ack, err := c.Push(ctx, a.Name, cfg)
			if err != nil {
				failed = true
				fmt.Printf("%s: FAILED: %v\n", a.Name, err)
				continue
			}
			fmt.Printf("%s: seq %d status %d\n", a.Name, ack.Seq, ack.Status)
		}
		if failed {
			defer os.Exit(1)
		}
	}
	if *poll {
		c.Poll(ctx)
		out, _ := json.MarshalIndent(c.Statuses(), "", "  ")
		fmt.Println(string(out))
	}
}
