"""Distinct publication instants without moving the fixture's media/sample clock."""
import math


def sync(agent):
    clock = agent.now
    at = clock()
    sent = math.nextafter(agent._test_report_at, math.inf) if getattr(agent, '_test_clock_at', None) == at else at
    agent._test_clock_at, agent._test_report_at = at, sent
    agent.now = lambda: sent
    try:
        return agent.sync()
    finally:
        agent.now = clock
