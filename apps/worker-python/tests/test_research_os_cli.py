import json

from typer.testing import CliRunner

from dehps import cli


def test_research_os_resolve_cli_emits_read_only_digest_addressed_snapshot(tmp_path) -> None:
    manifest = {
        "schema_version": "research-os-control-plane-v1",
        "goals": [
            {
                "goal_key": "research",
                "semantic_version": "1.0.0",
                "objective_class": "prediction_quality",
                "status": "active",
                "success_evidence": ["reviewed_bundle"],
                "owner_lane": "research",
            }
        ],
        "tasks": [
            {
                "task_key": "replay",
                "goal_key": "research",
                "task_type": "replay",
                "lane": "research",
            },
            {
                "task_key": "evaluation",
                "goal_key": "research",
                "task_type": "evaluation",
                "lane": "research",
                "dependencies": [
                    {"dependency_type": "external_event", "target_key": "draw:2026083"}
                ],
            },
        ],
    }
    input_path = tmp_path / "manifest.json"
    input_path.write_text(json.dumps(manifest))

    result = CliRunner().invoke(cli.app, ["research-os", "resolve", "--input", str(input_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["artifact_type"] == "resolution_snapshot"
    assert len(payload["manifest_digest"]) == 64
    assert len(payload["snapshot_digest"]) == 64
    assert payload["dispatch_performed"] is False
    assert payload["production_impact"] == "none"
    assert payload["state_counts"] == {"external_wait": 1, "ready": 1}
    assert [item["task_key"] for item in payload["ready_queue"]] == ["replay"]


def test_research_os_resolve_cli_fails_closed_on_unknown_schema(tmp_path) -> None:
    input_path = tmp_path / "manifest.json"
    input_path.write_text(json.dumps({"schema_version": "unknown", "goals": [], "tasks": []}))

    result = CliRunner().invoke(cli.app, ["research-os", "resolve", "--input", str(input_path)])

    assert result.exit_code == 2
    assert "unsupported schema_version" in result.stderr
