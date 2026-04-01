import numpy as np

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
