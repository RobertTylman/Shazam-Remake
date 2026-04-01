import math
import numpy as np
import scipy.io.wavfile as wav
import scipy.signal as signal
import matplotlib.pyplot as plt

def load_audio(filepath: str):
    """Load a wav file and return sample rate and audio data."""
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

def process_audio_pipeline(filepath: str, frame_size: int = 4096, target_sr: int = 11025) -> tuple:
    """Run the entire audio processing pipeline from raw wav to spectrogram."""
    sample_rate, audio_data = load_audio(filepath)
    audio_mono = convert_to_mono(audio_data)
    audio_filtered = bandpass_filter(audio_mono, sample_rate, lowcut=20.0, highcut=5000.0)
    audio_resampled = resample_audio(audio_filtered, sample_rate, target_sr)
    
    spectrogram = generate_spectrogram(audio_resampled, target_sr, frame_size=frame_size)
    
    return spectrogram, target_sr

if __name__ == "__main__":
    # Test block to generate a sample dummy audio and test the pipeline
    test_sr = 44100
    t = np.linspace(0, 2, 2 * test_sr, endpoint=False) # 2 seconds
    # Generate a dummy chord: 400Hz + 800Hz
    test_audio = np.sin(2 * np.pi * 400 * t) + 0.5 * np.sin(2 * np.pi * 800 * t)
    
    # Write a temporary 16-bit PCM WAV to disk to test ingestion
    test_wav = "/tmp/test_shazam_audio.wav"
    wav.write(test_wav, test_sr, (test_audio * 32767).astype(np.int16))
    print(f"Created dummy audio chunk at {test_wav}")
    
    # Run the pipeline
    spec, sr = process_audio_pipeline(test_wav)
    print(f"Pipeline executed successfully.")
    print(f"Spectrogram shape: {spec.shape} (Freq Bins x Time Frames)")
    print(f"At {sr}Hz with 4096 framing, frequency resolution is ~{sr/4096:.2f}Hz per bin.")

