// Command stripfuncs removes named top-level functions (and their doc comments) from a Go file.
//
//	go run ./tools/stripfuncs FILE FuncA FuncB ...
//
// taskgen uses it to take the tests that would reveal a planted bug out of the agent's copy of the
// code. The originals still run at grading time.
package main

import (
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/token"
	"os"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintln(os.Stderr, "usage: stripfuncs FILE FUNC...")
		os.Exit(2)
	}
	path, names := os.Args[1], map[string]bool{}
	for _, n := range os.Args[2:] {
		names[n] = true
	}
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, path, nil, parser.ParseComments)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	cmap := ast.NewCommentMap(fset, f, f.Comments)
	var kept []ast.Decl
	for _, d := range f.Decls {
		if fd, ok := d.(*ast.FuncDecl); ok && fd.Recv == nil && names[fd.Name.Name] {
			delete(names, fd.Name.Name)
			continue
		}
		kept = append(kept, d)
	}
	if len(names) > 0 {
		fmt.Fprintf(os.Stderr, "not found in %s: %v\n", path, names)
		os.Exit(1)
	}
	f.Decls = kept
	f.Comments = cmap.Filter(f).Comments()
	out, err := os.Create(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer out.Close()
	if err := format.Node(out, fset, f); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
