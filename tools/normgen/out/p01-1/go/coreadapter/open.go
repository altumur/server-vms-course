// Package coreadapter: Open — yours (ADR-0125 addendum (4)). The kit puts this stub once and never overwrites it.
package coreadapter

import "errors"

// Open — a fresh core for one scenario: build your store by cfg and return Wrap(cfg, yourHandler, yourClose).
// yourHandler implements apidoor.Handler[*Request] (Get, List, Write, Rights, Status, Join, Leave, Metrics,
// QueryRefused) over your core of Н3; the kit's frame and routes are in Wrap.
func Open(cfg Config) (Core, error) {
	return nil, errors.New("coreadapter: not implemented")
}
