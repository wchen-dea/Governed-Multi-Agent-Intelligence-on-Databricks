"""Application-level execution errors safe to expose to requesters."""


class GovernedExecutionError(Exception):
    """Reject an execution request with a governed, user-facing message."""
