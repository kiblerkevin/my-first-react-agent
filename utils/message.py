"""Simple message container for agent conversations."""


class Message:
    """A role-tagged message in a conversation."""

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content
