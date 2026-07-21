package toy

// Calc holds a trivial method receiver for Type.method-style qnames.
type Calc struct {
	N int
}

// Scale calls Add.
func (c *Calc) Scale(v int) int {
	return Add(v, 0)
}

// Run uses Scale and Compute.
func (c *Calc) Run(a, b int) int {
	return c.Scale(Compute(a, b))
}
