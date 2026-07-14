import json

from dehps.forward_runtime.models import ForwardQueueAction, ForwardRuntimeState, ForwardRuntimeStatus
from dehps.forward_runtime.resident import ResidentForwardRuntime, ResidentForwardRuntimeConfig


class Service:
    def status(self):
        return {
            "runtime": "forward_validation",
            "research_runtime_blocked": False,
            "state": ForwardRuntimeState(
                status=ForwardRuntimeStatus.FORWARD_WAITING,
                action=ForwardQueueAction.WAITING,
                pending_issue="2026080",
                observed_issue=None,
                event_key=None,
                reason_code="no_pending_event",
            ),
        }


def test_resident_forward_runtime_records_forward_waiting_state(tmp_path) -> None:
    resident = ResidentForwardRuntime(
        service=Service(),  # type: ignore[arg-type]
        config=ResidentForwardRuntimeConfig(
            interval_seconds=0,
            max_checks=2,
            lock_path="forward-runtime.lock",
            pid_path="forward-runtime.pid",
            state_path="forward-runtime-state.json",
        ),
        root_dir=tmp_path,
    )

    state = resident.run()

    assert state["checks_completed"] == 2
    assert state["status"] == "stopped"
    persisted = json.loads((tmp_path / "forward-runtime-state.json").read_text(encoding="utf-8"))
    assert persisted["last_status"]["state"]["status"] == "forward_waiting"
    assert persisted["last_status"]["research_runtime_blocked"] is False
