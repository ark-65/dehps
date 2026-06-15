# DEHPS Theory

DEHPS studies how humans can reason about huge discrete event spaces without claiming that random events become predictable.

For the 双色球 red-ball demo, every legal six-number combination has the same mathematical probability before a draw. DEHPS instead asks a different question: which combinations look structurally natural, which are easily described by short rules, and how do strategy filters behave when judged against history?

The core loop is:

1. Encode combinations as features.
2. Score structural plausibility.
3. Define a strategy filter.
4. Backtest against historical draws.
5. Report keep rate, coverage rate, lift, and failure modes.

Historical backtests do not prove future predictive power. They are a way to reject weak or overfit hypotheses.

