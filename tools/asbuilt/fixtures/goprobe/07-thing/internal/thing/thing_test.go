package thing

import (
	"os"
	"testing"
)

// Test files are outside the static snapshot: nothing here may appear in it.
func TestIgnored(t *testing.T) {
	if os.Getenv("TEST_ONLY") != "" {
		t.Fatal(fault(418, "teapot"))
	}
}
