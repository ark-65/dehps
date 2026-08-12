from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from dehps.notifications.mail import (
    MailDeliveryError,
    MailDeliveryReceipt,
    QqMailConfig,
)
from dehps.notifications.post_draw_evaluation import (
    PostDrawDeliveryStateError,
    PostDrawEvaluationDeliveryLedger,
    PostDrawEvaluationNotificationService,
    PostDrawEvaluationReportError,
    compile_post_draw_evaluation_report,
    write_post_draw_evaluation_artifacts,
)

RECIPIENT = "recipient@example.com"
AUTHORIZATION_CODE = "abcdefghijklmnop"


@pytest.fixture
def inactive_legacy_retirement(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "dehps.prediction.v2.retirement.DEFAULT_ACTIVATION_PATH",
        tmp_path / "legacy-retirement-not-activated.json",
    )


pytestmark = pytest.mark.usefixtures("inactive_legacy_retirement")


def _row(
    line_key: str,
    *,
    model_rank: int,
    export_rank: int | None,
    red5_rank: int | None,
) -> dict:
    return {
        "evaluation_key": f"eval:{line_key}:2026083",
        "prediction_run_key": f"{line_key}:2026083:snapshot-{line_key}",
        "evaluation_run_key": f"forward-eval:{line_key}:2026083",
        "prediction_ranking_contract": "strict_v1",
        "run_ranking_contract": "strict_v1",
        "line_key": line_key,
        "line_label": line_key,
        "line_kind": line_key,
        "snapshot_key": f"snapshot-{line_key}",
        "run_id": "training-run-1",
        "source_round_index": 8,
        "as_of_issue": "2026082",
        "predicted_issue": "2026083",
        "actual_draw_date": "2026-07-21",
        "actual_red_numbers": [1, 6, 12, 19, 26, 31],
        "actual_blue_number": 9,
        "current_actual_draw_date": "2026-07-21",
        "current_actual_red_numbers": [1, 6, 12, 19, 26, 31],
        "current_actual_blue_number": 9,
        "exact_rank": export_rank,
        "hit_top_100": export_rank is not None and export_rank <= 100,
        "hit_top_1000": export_rank is not None and export_rank <= 1000,
        "hit_top_10000": export_rank is not None and export_rank <= 10000,
        "red5_rank": red5_rank,
        "red5_numbers": [1, 6, 12, 19, 26, 33] if red5_rank is not None else None,
        "hit_red5_top_100": red5_rank is not None and red5_rank <= 100,
        "hit_red5_top_1000": red5_rank is not None and red5_rank <= 1000,
        "hit_red5_top_10000": red5_rank is not None and red5_rank <= 10000,
        "candidate_count": 10000,
        "prediction_candidate_count": 10000,
        "persisted_candidate_count": 10000,
        "top_n": 10000,
        "snapshot_generated_at": "2026-07-21T09:00:00+00:00",
        "evaluated_at": "2026-07-21T13:46:00+00:00",
        "status": "evaluated",
        "prediction_status": "evaluated",
        "evaluation_run_status": "completed",
        "config_hash": f"config-{line_key}",
        "prediction_fingerprint": f"fingerprint-{line_key}",
        "prediction_metadata": {},
        "summary": {
            "leakage_passed": True,
            "matched_red_count_by_cutoff": {
                "top_100": {"6": int(export_rank is not None and export_rank <= 100), "5": 1},
                "top_1000": {"6": int(export_rank is not None and export_rank <= 1000), "5": 4},
                "top_10000": {"6": int(export_rank is not None), "5": 23},
            },
            "ranking_audit": {
                "protocol": "forward-actual-ranking-path-v1",
                "issue": "2026083",
                "line_key": line_key,
                "prediction_run_key": f"{line_key}:2026083:snapshot-{line_key}",
                "snapshot_key": f"snapshot-{line_key}",
                "actual_reds": [1, 6, 12, 19, 26, 31],
                "ranking_contract": "strict_v1",
                "legal_sample_space": 1107568,
                "generated": True,
                "passed_hard_filters": True,
                "initial_score_rank": 300000,
                "model_score_rank": model_rank,
                "final_export_rank": export_rank,
                "eliminated_stage": "model_score" if export_rank is None else None,
                "elimination_reason": (
                    "model_score_rank_below_export_cutoff" if export_rank is None else None
                ),
            },
            "evaluation_artifact": {
                "status": "verified",
                "evaluation_contract": "evaluation.v1.0.0",
                "artifact_digest": f"artifact-{line_key}",
                "source_runtime_envelope_digest": f"runtime-{line_key}",
                "candidate_package_digest": f"candidate-{line_key}",
                "automatic_promotion_allowed": False,
            },
        },
    }


def _rows() -> list[dict]:
    return [
        _row("static_100", model_rank=75, export_rank=75, red5_rank=12),
        _row("dynamic_kdj", model_rank=12000, export_rank=None, red5_rank=875),
        _row("dynamic_kdj_near", model_rank=8000, export_rank=8000, red5_rank=1393),
    ]


class RecordingMailService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    def send(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise MailDeliveryError("sanitized SMTP failure")
        return MailDeliveryReceipt(
            message_id="<post-draw@example.com>",
            sender="sender@qq.com",
            recipient=kwargs["recipient"],
        )


def _config() -> QqMailConfig:
    return QqMailConfig(
        address="sender@qq.com",
        authorization_code=AUTHORIZATION_CODE,
        recipient=RECIPIENT,
    )


def test_compiler_renders_detailed_three_line_report_without_scores() -> None:
    report = compile_post_draw_evaluation_report(_rows(), recipient=RECIPIENT)

    assert report.issue == "2026083"
    assert report.subject == "[DEHPS][开奖后评估] 双色球 2026083 三线命中与排名详报"
    assert len(report.payload["lines"]) == 3
    assert "全空间模型排名 75/1,107,568" in report.text
    assert "冻结 Top10,000 导出排名：第 75 名" in report.text
    assert "精确6红 Top100：命中" in report.text
    assert "红5最佳排名：第 12 名" in report.text
    assert "“精确6红”与“红5”" in report.text
    assert "score" not in report.text.lower()
    assert report.html.startswith("<!doctype html><html><body><pre>")


def test_report_digest_changes_when_accepted_evidence_changes() -> None:
    original = compile_post_draw_evaluation_report(_rows(), recipient=RECIPIENT)
    changed_rows = _rows()
    changed_rows[0]["summary"]["ranking_audit"]["initial_score_rank"] = 299999
    changed = compile_post_draw_evaluation_report(changed_rows, recipient=RECIPIENT)

    assert changed.report_digest != original.report_digest
    assert changed.delivery_key != original.delivery_key


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda rows: rows.pop(), "exactly one row per line"),
        (lambda rows: rows[0].update(as_of_issue="2026083"), "leakage guard"),
        (lambda rows: rows[0].update(candidate_count=9999), "incomplete"),
        (
            lambda rows: rows[0].update(current_actual_blue_number=8),
            "disagrees with current official history",
        ),
        (lambda rows: rows[0].update(hit_top_100=False), "inconsistent hit_top_100"),
        (
            lambda rows: rows[0]["summary"]["ranking_audit"].update(final_export_rank=76),
            "export rank evidence disagrees",
        ),
    ],
)
def test_compiler_fails_closed_on_incomplete_or_inconsistent_evidence(mutate, message: str) -> None:
    rows = _rows()
    mutate(rows)

    with pytest.raises(PostDrawEvaluationReportError, match=message):
        compile_post_draw_evaluation_report(rows, recipient=RECIPIENT)


def test_digest_addressed_artifacts_are_stable(tmp_path: Path) -> None:
    report = compile_post_draw_evaluation_report(_rows(), recipient=RECIPIENT)

    first = write_post_draw_evaluation_artifacts(report, tmp_path)
    second = write_post_draw_evaluation_artifacts(report, tmp_path)

    assert first == second
    payload = json.loads(first[0].read_text())
    assert payload["report_digest"] == report.report_digest
    assert first[1].read_text() == report.text


def test_delivery_is_idempotent_after_sent_state(tmp_path: Path) -> None:
    mail = RecordingMailService()
    service = PostDrawEvaluationNotificationService(
        _config(),
        mail_service=mail,  # type: ignore[arg-type]
        ledger=PostDrawEvaluationDeliveryLedger(tmp_path / "ledger.json"),
        output_dir=tmp_path / "reports",
    )

    first = service.deliver(_rows())
    second = service.deliver(_rows())

    assert first.status == "sent"
    assert second.status == "already_sent"
    assert len(mail.calls) == 1
    assert Path(first.json_path).exists()
    assert Path(first.text_path).exists()


def test_ambiguous_smtp_failure_is_never_retried(tmp_path: Path) -> None:
    mail = RecordingMailService(fail=True)
    service = PostDrawEvaluationNotificationService(
        _config(),
        mail_service=mail,  # type: ignore[arg-type]
        ledger=PostDrawEvaluationDeliveryLedger(tmp_path / "ledger.json"),
        output_dir=tmp_path / "reports",
    )

    with pytest.raises(MailDeliveryError, match="sanitized"):
        service.deliver(_rows())
    with pytest.raises(PostDrawDeliveryStateError, match="uncertain"):
        service.deliver(_rows())

    assert len(mail.calls) == 1


def test_report_rejects_duplicate_accepted_line() -> None:
    rows = _rows()
    rows.append(copy.deepcopy(rows[0]))

    with pytest.raises(PostDrawEvaluationReportError, match="exactly one row per line"):
        compile_post_draw_evaluation_report(rows, recipient=RECIPIENT)
