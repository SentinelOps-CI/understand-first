// Package app imports mathutil and calls it via the default package name.
package app

import "example.com/uf/go_crosspkg/mathutil"

// Run calls mathutil.Add across packages (AST invent-free when unique).
func Run(a, b int) int {
	return mathutil.Add(a, b)
}

// RunScale calls mathutil.Scale.
func RunScale(n int) int {
	return mathutil.Scale(n, 2)
}
