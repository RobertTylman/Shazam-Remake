document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const loaderContainer = document.getElementById('loader-container');
    const resultsSection = document.getElementById('results-section');
    const resultImage = document.getElementById('result-image');
    const resetBtn = document.getElementById('reset-btn');

    // --- Event Listeners for Drag and Drop ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight drop zone
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('dragover');
        }, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }, false);

    // Handle click to browse
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle selected files
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length === 0) return;
        
        const file = files[0];
        
        // Basic validation
        if (!file.type.startsWith('audio/') && !file.name.match(/\.(wav|m4a|mp3)$/i)) {
            alert('Please upload an audio file (.wav, .m4a, .mp3)');
            return;
        }

        uploadAndProcessFile(file);
    }

    async function uploadAndProcessFile(file) {
        // UI State: Uploading / Processing
        dropZone.classList.add('hidden');
        resultsSection.classList.add('hidden');
        loaderContainer.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server returned status: ${response.status}`);
            }

            // Parse API response
            const data = await response.json();

            // Display Results
            resultImage.src = data.image;
            
            // Hydrate Tracking Telemetry
            document.getElementById('stat-duration').textContent = data.duration.toFixed(2) + 's';
            document.getElementById('stat-peaks').textContent = data.peaks.toLocaleString();
            document.getElementById('stat-frames').textContent = data.num_frames.toLocaleString();
            document.getElementById('stat-frame-size').textContent = data.frame_size.toLocaleString();
            document.getElementById('stat-hop-size').textContent = data.hop_size.toLocaleString();
            document.getElementById('stat-lowest-hz').textContent = data.lowest_hz + ' Hz';
            document.getElementById('stat-highest-hz').textContent = data.highest_hz.toFixed(1) + ' Hz';
            
            // UI State: Complete
            loaderContainer.classList.add('hidden');
            resultsSection.classList.remove('hidden');
            
            // Scroll to results smoothly if needed
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (error) {
            console.error('Error processing audio:', error);
            alert('Failed to process the audio file. Please ensure the backend is running and the file is valid.');
            
            // Revert State on error
            loaderContainer.classList.add('hidden');
            dropZone.classList.remove('hidden');
            fileInput.value = ''; // clear input
        }
    }

    // Reset workflow
    resetBtn.addEventListener('click', () => {
        // Clear old image from memory
        URL.revokeObjectURL(resultImage.src);
        resultImage.src = '';
        fileInput.value = '';
        
        // Go back to drop zone
        resultsSection.classList.add('hidden');
        dropZone.classList.remove('hidden');
        
        // Scroll back to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
});
