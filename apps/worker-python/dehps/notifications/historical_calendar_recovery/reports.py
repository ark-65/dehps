"""Existing exact accounting with explicit original versus actual calendars."""

import html

from dehps.notifications.historical_returns.reports import report as returns_report

from .contract import EVENT, digest


def report(seal, label, payout, *, planned_at=None, source_sha256):
    output = returns_report(
        {
            "original": {
                "artifact": {"value": {"seal": seal, "label": label}},
                "artifact_sha256": source_sha256,
            },
            "payout": payout,
        }
    )
    note = (
        "原计划开奖时间："
        + str(planned_at or seal["draw_at"])
        + "；实际开奖时间："
        + label["draw_at"]
        + "。\n"
        "日历恢复不增加科学证据信用；原始封存和缺口保持原样。\n"
    )
    output["text"] = note + output["text"].replace(
        "原始复盘摘要：", "本次登记输入摘要："
    )
    output["html"] = (
        "<p>"
        + html.escape(note)
        + "</p>"
        + output["html"].replace("原始复盘摘要：", "本次登记输入摘要：")
    )
    return output


def summary(values):
    ordered = sorted(values, key=lambda v: v["issue"])
    subject = "[DEHPS 遗漏学习·实验] 2026114—116 汇总复盘"
    lead = (
        subject
        + "\n\n本次合并恢复三期报告。缺少真实赛前封存的期次保留缺口，不计算假想收益。\n"
    )
    return {
        "event_id": EVENT,
        "source_reports_sha256": digest(ordered),
        "subject": subject,
        "text": lead + "\n\n".join(v["report"]["text"] for v in ordered),
        "html": "<h2>"
        + html.escape(subject)
        + "</h2><p>"
        + html.escape(lead)
        + "</p>"
        + "".join(v["report"]["html"] for v in ordered),
    }
