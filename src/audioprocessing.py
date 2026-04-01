import math
import numpy as np
import scipy.io.wavfile as wav
import scipy.signal as signal
import os
import subprocess
import tempfile
import sys

def load_audio(filepath: str):
    """Load an audio file and return sample rate and audio data."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"\nERROR: Could not find the file '{filepath}'. Please check for typos and ensure the file exists at the given path.")
        
    if not filepath.lower().endswith('.wav'):
        # Create a temporary wav file
        fd, temp_wav = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        
        try:
            # Use ffmpeg to convert to wav
            subprocess.run(['ffmpeg', '-y', '-i', filepath, temp_wav], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            sample_rate, data = wav.read(temp_wav)
        finally:
            os.remove(temp_wav)
    else:
        sample_rate, data = wav.read(filepath)
        
    # Convert to float32 for safer math operations
    data = data.astype(np.float32)
    return sample_rate, data

def convert_to_mono(audio_data: np.ndarray) -> np.ndarray:
    """Convert stereo audio to mono by averaging channels."""
    if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
        # Average across channels
        return np.mean(audio_data, axis=1)
    return audio_data

def bandpass_filter(audio_data: np.ndarray, sample_rate: int, lowcut: float = 20.0, highcut: float = 5000.0, order: int = 4):
    """Apply a Butterworth bandpass filter."""
    nyquist = 0.5 * sample_rate
    low = lowcut / nyquist
    high = highcut / nyquist
    
    # Generate filter coefficients
    b, a = signal.butter(order, [low, high], btype='band')
    
    # Apply filter using forward-backward filtering to avoid phase shift
    filtered_audio = signal.filtfilt(b, a, audio_data)
    return filtered_audio

def resample_audio(audio_data: np.ndarray, original_sr: int, target_sr: int = 11025) -> np.ndarray:
    """Resample audio to the target sample rate."""
    if original_sr == target_sr:
        return audio_data
        
    g = math.gcd(target_sr, original_sr)
    up = target_sr // g
    down = original_sr // g
    
    # resample_poly is usually better for audio than standard resample (FFT-based)
    resampled_audio = signal.resample_poly(audio_data, up, down)
    return resampled_audio

def generate_spectrogram(audio_data: np.ndarray, sample_rate: int, frame_size: int = 4096, overlap_ratio: float = 0.5):
    """Generate a spectrogram using overlapping Hamming windows and FFT."""
    step_size = int(frame_size * (1 - overlap_ratio))
    
    # Calculate how many frames we will have
    num_frames = 1 + int((len(audio_data) - frame_size) / step_size)
    
    # If the audio is shorter than one frame, pad or error out
    if num_frames < 1:
        raise ValueError("Audio is too short for the given frame size.")
        
    # Create the Hamming window
    window = np.hamming(frame_size)
    
    # List to hold the magnitude spectra
    spectrogram = []
    
    for i in range(num_frames):
        start = i * step_size
        end = start + frame_size
        
        # Extract the frame
        frame = audio_data[start:end]
        
        # Apply the Hamming window
        windowed_frame = frame * window
        
        # Compute the Real FFT (since audio is real-valued)
        # rfft returns frame_size // 2 + 1 coefficients
        fft_result = np.fft.rfft(windowed_frame)
        
        # Compute the power/magnitude spectrogram (take absolute value)
        magnitude = np.abs(fft_result)
        
        spectrogram.append(magnitude)
    
    # Convert list of arrays to 2D numpy array and return transposed
    # Transpose so time is x-axis (columns) and frequency is y-axis (rows)
    return np.array(spectrogram).T

def process_audio_pipeline(filepath: str, frame_size: int = 1024, target_sr: int = 11025) -> tuple:
    """Run the entire audio processing pipeline from raw wav to spectrogram."""
    sample_rate, audio_data = load_audio(filepath)
    audio_mono = convert_to_mono(audio_data)
    audio_filtered = bandpass_filter(audio_mono, sample_rate, lowcut=20.0, highcut=5000.0)
    audio_resampled = resample_audio(audio_filtered, sample_rate, target_sr)
    
    spectrogram = generate_spectrogram(audio_resampled, target_sr, frame_size=frame_size)
    
    return spectrogram, target_sr

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    try:
        from src.fingerprinting import extract_peaks
    except ImportError:
        from fingerprinting import extract_peaks
    
    if len(sys.argv) > 1:
        test_wav = sys.argv[1]
        print(f"Loading provided audio: {test_wav}")
        test_sr, full_audio = load_audio(test_wav)
        
        # If stereo, convert to mono right away for plotting the waveform
        if len(full_audio.shape) > 1 and full_audio.shape[1] > 1:
            full_audio = np.mean(full_audio, axis=1)
            
        t = np.linspace(0, len(full_audio) / test_sr, len(full_audio), endpoint=False)
    else:
        # Test block to generate a sample dummy audio and test the pipeline
        test_sr = 44100
        t = np.linspace(0, 2, 2 * test_sr, endpoint=False) # 2 seconds
        # Generate a dummy chord: 400Hz + 800Hz
        full_audio = np.sin(2 * np.pi * 400 * t) + 0.5 * np.sin(2 * np.pi * 800 * t)
        
        # Write a temporary 16-bit PCM WAV to disk to test ingestion
        test_wav = "/tmp/test_shazam_audio.wav"
        wav.write(test_wav, test_sr, (full_audio * 32767).astype(np.int16))
        print(f"Created dummy audio chunk at {test_wav}")
    
    # Run the pipeline
    frame_size = 1024 
    spec, sr = process_audio_pipeline(test_wav, frame_size=frame_size)
    print(f"Pipeline executed successfully.")
    print(f"Spectrogram shape: {spec.shape} (Freq Bins x Time Frames)")
    print(f"At {sr}Hz with {frame_size} framing, frequency resolution is ~{sr/frame_size:.2f}Hz per bin.")
    
    # Extract peaks
    # The default coefficient is 1.0. We collect all standalone points above the global mean.
    peaks = extract_peaks(spec, coefficient=1.0)
    print(f"Extracted {len(peaks)} constellation peaks from the entire spectrogram.")
    
    step_size = int(frame_size * 0.5) # 50% overlap

    # ----- Plotting -----
    # Render the full song natively
    max_plot_seconds = len(full_audio) / test_sr
    
    peak_times = [p[0] for p in peaks]
    peak_freqs = [p[1] for p in peaks]
    
    time_bins_in_seconds = [idx * (step_size / sr) for idx in peak_times]
    freq_bins_in_hz = [idx * (sr / frame_size) for idx in peak_freqs]

    spec_db = 10 * np.log10(spec + 1e-10)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8), gridspec_kw={'height_ratios': [2, 1]})
    
    # Spectrogram Subplot (Top)
    im = ax1.imshow(spec_db, aspect='auto', origin='lower', cmap='viridis', 
               extent=[0, max_plot_seconds, 0, sr / 2])
    
    if peaks:
        ax1.scatter(time_bins_in_seconds, freq_bins_in_hz, color='red', marker='x', alpha=0.9, label='Extracted Peaks')
        ax1.legend(loc="upper right")
        
    ax1.set_title(f"Constellation Map over Spectrogram (Full Track: {max_plot_seconds:.1f}s)")
    ax1.set_ylabel("Frequency (Hz)")
    fig.colorbar(im, ax=ax1, format='%+2.0f dB')
    
    # Original Waveform Subplot (Bottom)
    ax2.plot(t, full_audio, color='blue', alpha=0.8)
    ax2.set_title(f"Original Time Domain Signal (Full Track: {max_plot_seconds:.1f}s)")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Amplitude")
    ax2.set_xlim([0, max_plot_seconds])
    
    plt.tight_layout()
    
    output_img = "/tmp/spectrogram_test.png"
    plt.savefig(output_img)
    print(f"Saved spectrogram plot with constellation map to {output_img}")

