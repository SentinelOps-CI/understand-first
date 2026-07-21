package toy

// RunShared calls Helper in the same package (cross-file, unique name).
// Regex path must leave this unqualified; AST path may qualify when unique.
func RunShared() string {
	return Helper()
}
