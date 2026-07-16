export const LEGACY_RANKING_CONTRACT = 'legacy_score_partition' as const;
export const STRICT_RANKING_CONTRACT = 'strict_v1' as const;

export type RankingContract = typeof LEGACY_RANKING_CONTRACT | typeof STRICT_RANKING_CONTRACT;

export function normalizeRankingContract(value: unknown): RankingContract {
  if (value == null || String(value).trim() === '') return LEGACY_RANKING_CONTRACT;
  const normalized = String(value).trim();
  if (normalized === LEGACY_RANKING_CONTRACT || normalized === STRICT_RANKING_CONTRACT) return normalized;
  throw new Error(`unknown ranking contract: ${normalized}`);
}
