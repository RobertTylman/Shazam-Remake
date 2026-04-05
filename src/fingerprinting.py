import numpy as np
from typing import List, Tuple

def extract_peaks(spectrogram: np.ndarray, coefficient: float = 1.0) -> list:
    """
    Extracts standout frequency peaks from a 2D spectrogram to form a constellation map.
    
    Args:
        spectrogram: 2D numpy array [Frequency Bins (513) x Time Frames]
        coefficient: Threshold multiplier applied against the global mean.
        
    Returns:
        List of tuples: (time_frame_idx, freq_bin_idx)
    """
    # Define the 6 logarithmic band boundaries [lower, upper)
    # The specification ranges cover bin 0 to 511.
    bands = [
        (0, 10),
        (10, 20),
        (20, 40),
        (40, 80),
        (80, 160),
        (160, 512)
    ]
    
    num_freq_bins, num_time_frames = spectrogram.shape
    
    # Check if the spectrogram has enough bins for the defined bands
    if num_freq_bins < 512:
        raise ValueError(f"Spectrogram must have at least 512 frequency bins. Found only {num_freq_bins}.")
    
    # Step 1 & 2: Iterate through every time frame and every band to find the strongest bins
    all_local_max_magnitudes = []
    candidate_peaks = []
    
    for t_idx in range(num_time_frames):
        for lower_bound, upper_bound in bands:
            # Extract the specific frequency band for this time slice
            band_slice = spectrogram[lower_bound:upper_bound, t_idx]
            
            # Find the strongest bin in this band
            max_val = np.max(band_slice)
            max_idx_in_band = np.argmax(band_slice)
            
            # Map index back to full spectrogram row index
            actual_freq_idx = lower_bound + max_idx_in_band
            
            candidate_peaks.append((t_idx, actual_freq_idx, max_val))
            all_local_max_magnitudes.append(max_val)
            
    # Step 3: Compute the global average value of all these powerful local max bins
    global_mean = np.mean(all_local_max_magnitudes)
    
    # Step 4: Filter out standalone peaks using the threshold
    threshold = global_mean * coefficient
    
    final_peaks = []
    for t_idx, f_idx, mag in candidate_peaks:
        if mag > threshold:
            final_peaks.append((t_idx, f_idx))
            
    return final_peaks


def _encode_hash_32(anchor_freq: int, target_freq: int, delta_time: int) -> int:
    """
    Pack (anchor_freq, target_freq, delta_time) into a compact 32-bit integer.

    Bit layout (MSB -> LSB):
    - anchor_freq: 9 bits  (0..511)
    - target_freq: 9 bits  (0..511)
    - delta_time: 14 bits  (0..16383)
    """
    if not (0 <= anchor_freq <= 511):
        raise ValueError(f"anchor_freq out of range [0, 511]: {anchor_freq}")
    if not (0 <= target_freq <= 511):
        raise ValueError(f"target_freq out of range [0, 511]: {target_freq}")
    if not (0 <= delta_time <= 16383):
        raise ValueError(f"delta_time out of range [0, 16383]: {delta_time}")

    return (
        ((anchor_freq & 0x1FF) << 23)
        | ((target_freq & 0x1FF) << 14)
        | (delta_time & 0x3FFF)
    )


def hashingAlgorithm(
    peaks: List[Tuple[int, int]],
    target_zone_time: int = 50,
    target_zone_freq: int = 80,
    max_targets_per_anchor: int = 5,
    include_metadata: bool = False
) -> list:
    """
    Build Shazam-style anchor/target hashes from constellation peaks.

    Each peak is treated as an anchor. For every anchor, up to
    `max_targets_per_anchor` nearby peaks are selected from a fixed target zone.
    For each anchor-target pair, compute:
      hash_2 = encode(anchor.freq, target.freq, target.time - anchor.time)

    Args:
        peaks: List of (time_frame_idx, freq_bin_idx) tuples.
        target_zone_time: Maximum forward time distance (in frames) for targets.
        target_zone_freq: Maximum absolute frequency-bin distance from anchor.
        max_targets_per_anchor: Number of target peaks to keep per anchor.

    Returns:
        If include_metadata is False:
            List of (hash_32, anchor_time_idx) tuples.
        If include_metadata is True:
            List of dict records with anchor/target coordinates and hash value.
    """
    if target_zone_time <= 0:
        raise ValueError("target_zone_time must be > 0")
    if target_zone_freq < 0:
        raise ValueError("target_zone_freq must be >= 0")
    if max_targets_per_anchor <= 0:
        raise ValueError("max_targets_per_anchor must be > 0")

    if not peaks:
        return []

    # Ensure deterministic order and forward-only pairing.
    sorted_peaks = sorted(peaks, key=lambda p: (p[0], p[1]))
    fingerprints: list = []
    n = len(sorted_peaks)

    for i in range(n):
        anchor_time, anchor_freq = sorted_peaks[i]
        targets_used = 0

        for j in range(i + 1, n):
            target_time, target_freq = sorted_peaks[j]
            delta_time = target_time - anchor_time

            # Since peaks are time-sorted, we can early-break once out of range.
            if delta_time > target_zone_time:
                break
            if delta_time <= 0:
                continue
            if abs(target_freq - anchor_freq) > target_zone_freq:
                continue

            hash_32 = _encode_hash_32(anchor_freq, target_freq, delta_time)
            if include_metadata:
                fingerprints.append({
                    "hash": hash_32,
                    "anchor_time": anchor_time,
                    "anchor_freq": anchor_freq,
                    "target_time": target_time,
                    "target_freq": target_freq,
                    "delta_time": delta_time
                })
            else:
                fingerprints.append((hash_32, anchor_time))
            targets_used += 1

            if targets_used >= max_targets_per_anchor:
                break

    return fingerprints
