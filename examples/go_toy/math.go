// Package toy is a small Go fixture for Understand-First Wave 19.
package toy

// Add returns the sum of a and b.
func Add(a, b int) int {
	return a + b
}

// Compute calls Add.
func Compute(x, y int) int {
	total := Add(x, y)
	return total
}

// Classify branches for keyword / AST complexity checks.
func Classify(n int) string {
	if n < 0 {
		return "neg"
	}
	for i := 0; i < n; i++ {
		if i > 10 && i < 20 {
			return "mid"
		}
	}
	switch n {
	case 0:
		return "zero"
	default:
		return "other"
	}
}

func helper() int {
	return 1
}

// processEvent mentions helper only inside a string — neither regex nor AST
// may invent a call edge from string contents.
func processEvent(msg string) string {
	_ = "helper()"
	return msg
}
