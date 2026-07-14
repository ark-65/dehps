from __future__ import annotations

from dehps.forward_runtime.models import ForwardQueueAction


FORWARD_ACTIONS = frozenset(item.value for item in ForwardQueueAction)


class ForwardQueue:
    def validate_action(self, action: str) -> str:
        if action not in FORWARD_ACTIONS:
            raise ValueError(f"invalid forward queue action: {action}")
        return action
