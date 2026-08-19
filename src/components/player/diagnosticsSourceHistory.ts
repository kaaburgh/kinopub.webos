export type HlsSourceState<T> = {
  hls: T;
  quality: string | null;
};

export type HlsSourceTransition<T> = {
  state: HlsSourceState<T>;
  change?: string;
};

function qualityLabel(quality: string | null) {
  return quality || 'unknown';
}

/**
 * Tracks which selected quality belongs to an HLS instance without treating a transient player
 * selection change as proof that the old instance actually switched.
 */
export function transitionHlsSource<T>(
  previous: HlsSourceState<T> | null,
  hls: T,
  selectedQuality: string | null,
): HlsSourceTransition<T> {
  if (!previous) {
    return { state: { hls, quality: selectedQuality } };
  }

  if (previous.hls !== hls) {
    return {
      state: { hls, quality: selectedQuality },
      change: `${qualityLabel(previous.quality)} -> ${qualityLabel(selectedQuality)}`,
    };
  }

  // The HLS object can become visible before the player exposes its initial quality label. Filling
  // that blank is safe; replacing an established label is not, until LEVEL_SWITCHED confirms it.
  return !previous.quality && selectedQuality ? { state: { hls, quality: selectedQuality } } : { state: previous };
}

/** A LEVEL_SWITCHED event is the evidence that an in-place selection became true on this instance. */
export function settleHlsSourceQuality<T>(
  previous: HlsSourceState<T> | null,
  hls: T,
  selectedQuality: string | null,
): HlsSourceState<T> | null {
  if (!previous || previous.hls !== hls || !selectedQuality) {
    return previous;
  }

  return previous.quality === selectedQuality ? previous : { hls, quality: selectedQuality };
}
