// Package peer belongs to a neighbouring lesson.
package peer

import "os"

// Down reports a synthetic peer state.
func Down() bool { return len(os.Args) > 99 }
