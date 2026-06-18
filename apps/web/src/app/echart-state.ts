export type LegendSelectionState = Record<string, boolean>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function boolRecord(value: unknown): LegendSelectionState {
  if (!isRecord(value)) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value).filter((entry): entry is [string, boolean] => typeof entry[1] === 'boolean'),
  );
}

function mergeLegendValue(value: unknown, selection: LegendSelectionState): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => mergeLegendValue(item, selection));
  }
  if (!isRecord(value)) {
    return value;
  }
  return {
    ...value,
    selected: {
      ...boolRecord(value['selected']),
      ...selection,
    },
  };
}

export function legendSelectionFromEvent(event: unknown): LegendSelectionState {
  if (!isRecord(event)) {
    return {};
  }
  return boolRecord(event['selected']);
}

export function mergeLegendSelection<T>(option: T | null, selection: LegendSelectionState): T | null {
  if (!option || !Object.keys(selection).length || !isRecord(option)) {
    return option;
  }
  const source = option as Record<string, unknown>;
  const legend = source['legend'];
  if (!legend) {
    return option;
  }
  return {
    ...source,
    legend: mergeLegendValue(legend, selection),
  } as T;
}
