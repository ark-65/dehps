from __future__ import annotations

from dehps.draw_sync.models import DrawAuditReport, stable_hash


DrawRecord = tuple[str, tuple[int, ...], int | None]


def history_fingerprint(draws: list[tuple[str, tuple[int, ...]]] | tuple[tuple[str, tuple[int, ...]], ...]) -> str:
    return stable_hash({"history": [(issue, tuple(numbers)) for issue, numbers in draws]})


class DrawDatabaseAuditor:
    def audit(self, draws: tuple[DrawRecord, ...]) -> DrawAuditReport:
        warnings: list[str] = []
        issues = [str(issue) for issue, _, _ in draws]
        duplicate_issue_count = len(issues) - len(set(issues))
        invalid_red_length_count = 0
        red_out_of_range_count = 0
        duplicate_red_numbers_count = 0
        blue_out_of_range_count = 0
        previous_int: int | None = None
        issue_order_ok = True
        for issue, red_numbers, blue_number in draws:
            if len(red_numbers) != 6:
                invalid_red_length_count += 1
            if len(set(red_numbers)) != len(red_numbers):
                duplicate_red_numbers_count += 1
            if any(number < 1 or number > 33 for number in red_numbers):
                red_out_of_range_count += 1
            if blue_number is not None and not 1 <= int(blue_number) <= 16:
                blue_out_of_range_count += 1
            if issue.isdigit():
                current = int(issue)
                if previous_int is not None and current < previous_int:
                    issue_order_ok = False
                previous_int = current
        if not draws:
            warnings.append("history_empty")
        passed = not (
            duplicate_issue_count
            or invalid_red_length_count
            or red_out_of_range_count
            or duplicate_red_numbers_count
            or blue_out_of_range_count
            or not issue_order_ok
            or not draws
        )
        latest_issue = max(issues, key=lambda value: int(value) if value.isdigit() else value) if issues else None
        return DrawAuditReport(
            passed=passed,
            latest_issue=latest_issue,
            history_fingerprint=history_fingerprint(tuple((issue, red) for issue, red, _ in draws)) if draws else None,
            draw_count=len(draws),
            duplicate_issue_count=duplicate_issue_count,
            invalid_red_length_count=invalid_red_length_count,
            red_out_of_range_count=red_out_of_range_count,
            duplicate_red_numbers_count=duplicate_red_numbers_count,
            blue_out_of_range_count=blue_out_of_range_count,
            issue_order_ok=issue_order_ok,
            warnings=tuple(warnings),
        )
