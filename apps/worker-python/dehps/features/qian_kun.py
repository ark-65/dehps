from __future__ import annotations

from collections import Counter
from typing import Iterable

from dehps.domain.combination import normalize_red_numbers

YANG_LINE = "—"
YIN_LINE = "- -"
QIAN_PATTERN = "111111"
KUN_PATTERN = "000000"
HEXAGRAMS_BY_PATTERN = {
    "111111": (1, "䷀", "乾卦"),
    "000000": (2, "䷁", "坤卦"),
    "100010": (3, "䷂", "屯卦"),
    "010001": (4, "䷃", "蒙卦"),
    "111010": (5, "䷄", "需卦"),
    "010111": (6, "䷅", "讼卦"),
    "010000": (7, "䷆", "师卦"),
    "000010": (8, "䷇", "比卦"),
    "111011": (9, "䷈", "小畜卦"),
    "110111": (10, "䷉", "履卦"),
    "111000": (11, "䷊", "泰卦"),
    "000111": (12, "䷋", "否卦"),
    "101111": (13, "䷌", "同人卦"),
    "111101": (14, "䷍", "大有卦"),
    "001000": (15, "䷎", "谦卦"),
    "000100": (16, "䷏", "豫卦"),
    "100110": (17, "䷐", "随卦"),
    "011001": (18, "䷑", "蛊卦"),
    "110000": (19, "䷒", "临卦"),
    "000011": (20, "䷓", "观卦"),
    "100101": (21, "䷔", "噬嗑卦"),
    "101001": (22, "䷕", "贲卦"),
    "000001": (23, "䷖", "剥卦"),
    "100000": (24, "䷗", "复卦"),
    "100111": (25, "䷘", "无妄卦"),
    "111001": (26, "䷙", "大畜卦"),
    "100001": (27, "䷚", "颐卦"),
    "011110": (28, "䷛", "大过卦"),
    "010010": (29, "䷜", "坎卦"),
    "101101": (30, "䷝", "离卦"),
    "001110": (31, "䷞", "咸卦"),
    "011100": (32, "䷟", "恒卦"),
    "001111": (33, "䷠", "遁卦"),
    "111100": (34, "䷡", "大壮卦"),
    "000101": (35, "䷢", "晋卦"),
    "101000": (36, "䷣", "明夷卦"),
    "101011": (37, "䷤", "家人卦"),
    "110101": (38, "䷥", "睽卦"),
    "001010": (39, "䷦", "蹇卦"),
    "010100": (40, "䷧", "解卦"),
    "110001": (41, "䷨", "损卦"),
    "100011": (42, "䷩", "益卦"),
    "111110": (43, "䷪", "夬卦"),
    "011111": (44, "䷫", "姤卦"),
    "000110": (45, "䷬", "萃卦"),
    "011000": (46, "䷭", "升卦"),
    "010110": (47, "䷮", "困卦"),
    "011010": (48, "䷯", "井卦"),
    "101110": (49, "䷰", "革卦"),
    "011101": (50, "䷱", "鼎卦"),
    "100100": (51, "䷲", "震卦"),
    "001001": (52, "䷳", "艮卦"),
    "001011": (53, "䷴", "渐卦"),
    "110100": (54, "䷵", "归妹卦"),
    "101100": (55, "䷶", "丰卦"),
    "001101": (56, "䷷", "旅卦"),
    "011011": (57, "䷸", "巽卦"),
    "110110": (58, "䷹", "兑卦"),
    "010011": (59, "䷺", "涣卦"),
    "110010": (60, "䷻", "节卦"),
    "110011": (61, "䷼", "中孚卦"),
    "001100": (62, "䷽", "小过卦"),
    "101010": (63, "䷾", "既济卦"),
    "010101": (64, "䷿", "未济卦"),
}


def qian_kun_bits(numbers: tuple[int, ...] | list[int]) -> tuple[int, int, int, int, int, int]:
    nums = normalize_red_numbers(numbers)
    return (
        nums[0] % 2,
        nums[1] % 2,
        nums[2] % 2,
        nums[3] % 2,
        nums[4] % 2,
        nums[5] % 2,
    )


def qian_kun_pattern(numbers: tuple[int, ...] | list[int]) -> str:
    return "".join(str(bit) for bit in qian_kun_bits(numbers))


def qian_kun_lines_from_pattern(pattern: str) -> list[str]:
    return [YANG_LINE if bit == "1" else YIN_LINE for bit in pattern]


def qian_kun_icon(pattern: str) -> str:
    hexagram = HEXAGRAMS_BY_PATTERN.get(pattern)
    return hexagram[1] if hexagram else ""


def qian_kun_label(pattern: str) -> str:
    hexagram = HEXAGRAMS_BY_PATTERN.get(pattern)
    if hexagram:
        return hexagram[2]
    yang_count = pattern.count("1")
    return f"{pattern} 阳{yang_count}/阴{6 - yang_count}"


def qian_kun_similarity(left: str, right: str) -> float:
    if len(left) != 6 or len(right) != 6:
        return 0.0
    return sum(left_bit == right_bit for left_bit, right_bit in zip(left, right, strict=True)) / 6


def qian_kun_distribution(
    history: Iterable[tuple[str, tuple[int, ...]]],
    *,
    recent_window: int = 100,
) -> dict:
    rows = list(history)
    counts = Counter(qian_kun_pattern(numbers) for _, numbers in rows)
    recent_counts = Counter(qian_kun_pattern(numbers) for _, numbers in rows[-recent_window:])
    total = len(rows)
    recent_total = min(recent_window, total)
    latest_issue = rows[-1][0] if rows else ""
    latest_numbers = rows[-1][1] if rows else ()
    latest_pattern = qian_kun_pattern(latest_numbers) if latest_numbers else ""

    all_patterns = sorted(set(counts) | set(recent_counts) | {QIAN_PATTERN, KUN_PATTERN})
    distribution = [
        {
            "pattern": pattern,
            "label": qian_kun_label(pattern),
            "icon": qian_kun_icon(pattern),
            "lines": qian_kun_lines_from_pattern(pattern),
            "count": counts.get(pattern, 0),
            "rate": counts.get(pattern, 0) / total if total else 0,
            "recent_count": recent_counts.get(pattern, 0),
            "recent_rate": recent_counts.get(pattern, 0) / recent_total if recent_total else 0,
        }
        for pattern in all_patterns
    ]
    distribution.sort(key=lambda item: (item["count"], item["recent_count"], item["pattern"]), reverse=True)

    return {
        "total_draws": total,
        "recent_window": recent_total,
        "latest_issue": latest_issue,
        "latest_numbers": list(latest_numbers),
        "latest_pattern": latest_pattern,
        "latest_label": qian_kun_label(latest_pattern) if latest_pattern else "",
        "latest_icon": qian_kun_icon(latest_pattern) if latest_pattern else "",
        "latest_lines": qian_kun_lines_from_pattern(latest_pattern) if latest_pattern else [],
        "qian_count": counts.get(QIAN_PATTERN, 0),
        "kun_count": counts.get(KUN_PATTERN, 0),
        "patterns": distribution,
    }
