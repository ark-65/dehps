# SSQ Physical Regime Notes

This note records the current evidence used by DEHPS to choose a conservative training window. It is not a claim that physical equipment creates a predictive edge.

## Current Documented Equipment Facts

- China Welfare Lottery public material describes the SSQ machine as a French Ryo-Catteau Myosotis mixing draw machine. Source: [谈个“球”：双色球您了解多少？](https://www.zhcw.com/c/2019-11-08/587657.shtml)
- Public equipment descriptions list the SSQ draw balls as 33 red balls and 16 blue balls made from natural rubber and closed-cell foam, with solid internal structure, about 25g weight, and about 50mm diameter. Source: [福彩摇奖设备全档案](https://lotto.sina.cn/2022-11-22/detail-imqmmthc5518343.d.html)
- The same public descriptions discuss multiple official ball sets, testing/cleaning/weight checks, and replacement cadence, but do not provide a frozen historical issue-by-issue material-change schedule. Source: [谈个“球”：双色球您了解多少？](https://www.zhcw.com/c/2019-11-08/587657.shtml)

## Modeling Policy

- Do not hard-code an unverified material-change issue.
- Use all available history for audit and distribution diagnostics.
- Use `current_regime_default` as the default training scope: the most recent 10 years ending at `as_of_issue`.
- If an authoritative issue-level equipment or material change table is found later, add a `custom_regime` boundary before changing training defaults.
