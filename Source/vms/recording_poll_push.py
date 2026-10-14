"""An unassigned camera polls its declared home with its own ephemeral credential."""
from w2cplatform.domain.placement import placed
from w2cplatform.domain.topology import poll_home
from .recording_books import Unconfirmed, read
from .recording_publication import member
from .role_tokens import RoleTokens


class PollPush:
    def __init__(self, pusher, door=None, *, role="camworker", env=None, clock=None):
        self.pusher = pusher
        self.tokens = RoleTokens(role, door=door, env=env, clock=clock)
        self.scope, self.route = None, None

    def clear(self):
        self.tokens.forget("poll", self.pusher.serial)
        self.scope, self.route = None, None

    def entry(self):
        from .recording_polls import observation, POLLS_PATH
        from w2cplatform.domain.memberbook import read as member_book
        p = self.pusher
        own = member(p.flash)
        try:
            if placed(p.flash, "rec", p.serial) is not None:
                self.clear()
                return None
            home = poll_home(p.flash, own)
        except (ValueError, TypeError, KeyError):
            self.clear()
            raise Unconfirmed("poll home is not confirmed") from None
        scope = own, home
        if self.scope != scope:
            self.clear()
            self.scope = scope
        try:
            fact = observation(p.flash, own, p.serial)
            route = tuple(fact.value["urls"])
        except Unconfirmed:
            # A complete withdrawal closes the old route. Unknown observations
            # cannot create a route; an already confirmed home may keep polling.
            facts = read(member_book(p.flash, POLLS_PATH, own), p.serial)
            if not facts.missing and not facts.entries:
                self.clear()
                return None
            if self.route is None:
                raise
            route = self.route
        token_scope = scope + (route,)
        token = self.tokens.get("poll", p.serial, token_scope)
        # A role request can wait while an operator changes topology or placement.
        if placed(p.flash, "rec", p.serial) is not None or member(p.flash) != own \
                or poll_home(p.flash, own) != home:
            self.clear()
            raise Unconfirmed("poll credential outlived its scope")
        try:
            current = observation(p.flash, own, p.serial)
        except Unconfirmed:
            facts = read(member_book(p.flash, POLLS_PATH, own), p.serial)
            if not facts.missing or self.route != route:
                self.clear()
                raise Unconfirmed("poll observation changed during token request") from None
        else:
            if tuple(current.value["urls"]) != route:
                self.clear()
                raise Unconfirmed("poll addresses changed during token request")
        self.route = route
        return {"cluster": home, "polls_only": True,
                "ingest": {"urls": list(route), "token_secret": token}}
