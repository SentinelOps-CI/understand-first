// Package aliasapp imports mathutil under an explicit alias.
package aliasapp

import mu "example.com/uf/go_crosspkg/mathutil"

// RunAliased calls Add via an import alias.
func RunAliased(a, b int) int {
	return mu.Add(a, b)
}
