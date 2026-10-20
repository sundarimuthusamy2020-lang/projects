/**
 * StegoCrypt Frontend Controller
 * Manages Tab navigation, AJAX file uploads, real-time capacity estimation,
 * side-by-side previews, and clipboard interaction.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Current state variables
    let currentCapacity = 0;
    let lastGeneratedStegoBlob = null;
    let lastGeneratedStegoFilename = '';

    // =========================================================
    // 1. Tab Navigation
    // =========================================================
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab');
            switchTab(targetId);
        });
    });

    function switchTab(tabId) {
        tabButtons.forEach(b => b.classList.toggle('active', b.getAttribute('data-tab') === tabId));
        tabPanes.forEach(p => p.classList.toggle('active', p.id === tabId));
    }

    // =========================================================
    // 2. Drag & Drop Helper Setup
    // =========================================================
    function setupDropZone(dropZone, fileInput, onFileSelected) {
        if (!dropZone || !fileInput) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
        });

        dropZone.addEventListener('drop', e => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                fileInput.files = files;
                onFileSelected(files[0]);
            }
        });

        dropZone.addEventListener('click', e => {
            if (e.target.closest('#encodeRemoveBtn') || e.target.closest('#decodeRemoveBtn')) return;
            fileInput.click();
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files && fileInput.files.length > 0) {
                onFileSelected(fileInput.files[0]);
            }
        });
    }

    // =========================================================
    // 3. Encode Tab Functionality
    // =========================================================
    const encodeDropZone = document.getElementById('encodeDropZone');
    const encodeImageInput = document.getElementById('encodeImageInput');
    const encodeDropContent = document.getElementById('encodeDropContent');
    const encodePreviewBox = document.getElementById('encodePreviewBox');
    const encodeImagePreview = document.getElementById('encodeImagePreview');
    const encodeFileName = document.getElementById('encodeFileName');
    const encodeFileDims = document.getElementById('encodeFileDims');
    const encodeRemoveBtn = document.getElementById('encodeRemoveBtn');

    const capacityBox = document.getElementById('capacityBox');
    const capacityValues = document.getElementById('capacityValues');
    const capacityBarFill = document.getElementById('capacityBarFill');
    const capacityInfoText = document.getElementById('capacityInfoText');

    const secretMessage = document.getElementById('secretMessage');
    const charCountLabel = document.getElementById('charCountLabel');
    const encodeForm = document.getElementById('encodeForm');
    const btnSubmitEncode = document.getElementById('btnSubmitEncode');

    const encodeEmptyState = document.getElementById('encodeEmptyState');
    const encodeSuccessContent = document.getElementById('encodeSuccessContent');
    const encodeStatusBadge = document.getElementById('encodeStatusBadge');

    const resPsnr = document.getElementById('resPsnr');
    const resMsgLen = document.getElementById('resMsgLen');
    const resDimensions = document.getElementById('resDimensions');
    const resCoverImg = document.getElementById('resCoverImg');
    const resStegoImg = document.getElementById('resStegoImg');
    const btnDownloadStego = document.getElementById('btnDownloadStego');
    const btnQuickTestDecode = document.getElementById('btnQuickTestDecode');

    // Setup Encode Dropzone
    setupDropZone(encodeDropZone, encodeImageInput, handleEncodeFile);

    function handleEncodeFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select a valid image file (PNG, JPG, BMP, WEBP).');
            return;
        }

        const reader = new FileReader();
        reader.onload = e => {
            encodeImagePreview.src = e.target.result;
            encodeFileName.textContent = file.name;
            encodeDropContent.style.display = 'none';
            encodePreviewBox.style.display = 'flex';

            // Determine dimensions
            const img = new Image();
            img.onload = () => {
                encodeFileDims.textContent = `${img.naturalWidth} x ${img.naturalHeight} px`;
            };
            img.src = e.target.result;

            // Query server for exact capacity
            estimateCapacity(file);
        };
        reader.readAsDataURL(file);
    }

    if (encodeRemoveBtn) {
        encodeRemoveBtn.addEventListener('click', e => {
            e.stopPropagation();
            resetEncodeUpload();
        });
    }

    function resetEncodeUpload() {
        encodeImageInput.value = '';
        encodeImagePreview.src = '';
        encodeDropContent.style.display = 'block';
        encodePreviewBox.style.display = 'none';
        capacityBox.style.display = 'none';
        currentCapacity = 0;
        updateCapacityMeter();
    }

    async function estimateCapacity(file) {
        const formData = new FormData();
        formData.append('image', file);

        try {
            const resp = await fetch('/api/capacity', {
                method: 'POST',
                body: formData
            });
            const data = await resp.json();
            if (data.success) {
                currentCapacity = data.capacity;
                capacityBox.style.display = 'block';
                capacityInfoText.textContent = `Image (${data.width}x${data.height}) can store up to ${data.capacity.toLocaleString()} characters.`;
                updateCapacityMeter();
            }
        } catch (err) {
            console.error('Failed to estimate capacity:', err);
        }
    }

    if (secretMessage) {
        secretMessage.addEventListener('input', () => {
            const len = secretMessage.value.length;
            charCountLabel.textContent = `${len.toLocaleString()} characters`;
            updateCapacityMeter();
        });
    }

    function updateCapacityMeter() {
        if (!capacityValues || !capacityBarFill) return;
        const msgLen = secretMessage ? secretMessage.value.length : 0;
        capacityValues.textContent = `${msgLen.toLocaleString()} / ${currentCapacity.toLocaleString()} chars`;

        if (currentCapacity > 0) {
            const percentage = Math.min(100, Math.round((msgLen / currentCapacity) * 100));
            capacityBarFill.style.width = `${percentage}%`;

            capacityBarFill.classList.remove('warning', 'danger');
            if (percentage >= 100) {
                capacityBarFill.classList.add('danger');
            } else if (percentage >= 80) {
                capacityBarFill.classList.add('warning');
            }
        } else {
            capacityBarFill.style.width = '0%';
        }
    }

    // Handle Encode Submission
    if (encodeForm) {
        encodeForm.addEventListener('submit', async e => {
            e.preventDefault();

            if (!encodeImageInput.files || encodeImageInput.files.length === 0) {
                alert('Please upload a cover image first.');
                return;
            }

            const message = secretMessage.value.trim();
            if (!message) {
                alert('Please enter a secret message to embed.');
                return;
            }

            if (currentCapacity > 0 && message.length > currentCapacity) {
                alert(`Message is too long (${message.length} chars). Maximum allowed is ${currentCapacity} characters.`);
                return;
            }

            // Set loading state
            setButtonLoading(btnSubmitEncode, true);

            const formData = new FormData();
            formData.append('image', encodeImageInput.files[0]);
            formData.append('message', message);

            try {
                const response = await fetch('/api/encode', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (!response.ok || !result.success) {
                    throw new Error(result.error || 'Failed to embed message.');
                }

                // Show results
                encodeEmptyState.style.display = 'none';
                encodeSuccessContent.style.display = 'block';
                if (encodeStatusBadge) encodeStatusBadge.style.display = 'inline-flex';

                resPsnr.textContent = `${result.psnr} dB`;
                resMsgLen.textContent = `${result.message_length} chars`;
                resDimensions.textContent = result.dimensions;

                resCoverImg.src = result.cover_image_url;
                resStegoImg.src = result.stego_image_url;

                btnDownloadStego.href = result.download_url;
                btnDownloadStego.setAttribute('download', result.stego_filename);

                lastGeneratedStegoFilename = result.stego_filename;

                // Cache stego image blob for quick decode
                fetch(result.stego_image_url)
                    .then(r => r.blob())
                    .then(blob => {
                        lastGeneratedStegoBlob = blob;
                    })
                    .catch(() => {});

                // Scroll results into view on mobile
                if (window.innerWidth < 900) {
                    document.getElementById('encodeResultsCard').scrollIntoView({ behavior: 'smooth' });
                }

            } catch (err) {
                alert(err.message || 'An error occurred during encoding.');
            } finally {
                setButtonLoading(btnSubmitEncode, false);
            }
        });
    }

    // Quick Test in Decode Tab
    if (btnQuickTestDecode) {
        btnQuickTestDecode.addEventListener('click', () => {
            if (!lastGeneratedStegoBlob && !resStegoImg.src) return;

            switchTab('tab-decode');

            // Set preview in decode tab
            decodeDropContent.style.display = 'none';
            decodePreviewBox.style.display = 'flex';
            decodeImagePreview.src = resStegoImg.src;
            decodeFileName.textContent = lastGeneratedStegoFilename || 'stego_image.png';
            decodeFileDims.textContent = resDimensions.textContent + ' px';

            // Populate file input with File object
            if (lastGeneratedStegoBlob) {
                const file = new File([lastGeneratedStegoBlob], lastGeneratedStegoFilename || 'stego_image.png', { type: 'image/png' });
                const container = new DataTransfer();
                container.items.add(file);
                decodeImageInput.files = container.files;
            }
        });
    }

    // =========================================================
    // 4. Decode Tab Functionality
    // =========================================================
    const decodeDropZone = document.getElementById('decodeDropZone');
    const decodeImageInput = document.getElementById('decodeImageInput');
    const decodeDropContent = document.getElementById('decodeDropContent');
    const decodePreviewBox = document.getElementById('decodePreviewBox');
    const decodeImagePreview = document.getElementById('decodeImagePreview');
    const decodeFileName = document.getElementById('decodeFileName');
    const decodeFileDims = document.getElementById('decodeFileDims');
    const decodeRemoveBtn = document.getElementById('decodeRemoveBtn');

    const decodeForm = document.getElementById('decodeForm');
    const btnSubmitDecode = document.getElementById('btnSubmitDecode');
    const decodeEmptyState = document.getElementById('decodeEmptyState');
    const decodeSuccessContent = document.getElementById('decodeSuccessContent');
    const decodeStatusBadge = document.getElementById('decodeStatusBadge');

    const decSourceFile = document.getElementById('decSourceFile');
    const decLength = document.getElementById('decLength');
    const decDims = document.getElementById('decDims');
    const extractedMessageText = document.getElementById('extractedMessageText');
    const btnCopyExtracted = document.getElementById('btnCopyExtracted');
    const copyBtnText = document.getElementById('copyBtnText');

    setupDropZone(decodeDropZone, decodeImageInput, handleDecodeFile);

    function handleDecodeFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select a valid image file.');
            return;
        }

        const reader = new FileReader();
        reader.onload = e => {
            decodeImagePreview.src = e.target.result;
            decodeFileName.textContent = file.name;
            decodeDropContent.style.display = 'none';
            decodePreviewBox.style.display = 'flex';

            const img = new Image();
            img.onload = () => {
                decodeFileDims.textContent = `${img.naturalWidth} x ${img.naturalHeight} px`;
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }

    if (decodeRemoveBtn) {
        decodeRemoveBtn.addEventListener('click', e => {
            e.stopPropagation();
            decodeImageInput.value = '';
            decodeImagePreview.src = '';
            decodeDropContent.style.display = 'block';
            decodePreviewBox.style.display = 'none';
        });
    }

    // Handle Decode Submission
    if (decodeForm) {
        decodeForm.addEventListener('submit', async e => {
            e.preventDefault();

            if (!decodeImageInput.files || decodeImageInput.files.length === 0) {
                alert('Please upload a stego image to extract secret data.');
                return;
            }

            setButtonLoading(btnSubmitDecode, true);

            const formData = new FormData();
            formData.append('image', decodeImageInput.files[0]);

            try {
                const response = await fetch('/api/decode', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (!response.ok || !result.success) {
                    throw new Error(result.error || 'Failed to extract hidden message.');
                }

                // Show decoded result
                decodeEmptyState.style.display = 'none';
                decodeSuccessContent.style.display = 'block';
                if (decodeStatusBadge) decodeStatusBadge.style.display = 'inline-flex';

                decSourceFile.textContent = result.filename;
                decLength.textContent = `${result.message_length} characters`;
                decDims.textContent = `${result.dimensions} px`;

                if (result.extracted_message && result.extracted_message.length > 0) {
                    extractedMessageText.textContent = result.extracted_message;
                } else {
                    extractedMessageText.textContent = '[No concealed secret message was detected in this image]';
                }

                if (window.innerWidth < 900) {
                    document.getElementById('decodeResultsCard').scrollIntoView({ behavior: 'smooth' });
                }

            } catch (err) {
                alert(err.message || 'An error occurred during extraction.');
            } finally {
                setButtonLoading(btnSubmitDecode, false);
            }
        });
    }

    // Copy Extracted Message to Clipboard
    if (btnCopyExtracted) {
        btnCopyExtracted.addEventListener('click', () => {
            const text = extractedMessageText.textContent;
            if (!text) return;

            navigator.clipboard.writeText(text).then(() => {
                copyBtnText.textContent = 'Copied!';
                btnCopyExtracted.classList.add('btn-success');
                btnCopyExtracted.classList.remove('btn-outline');

                setTimeout(() => {
                    copyBtnText.textContent = 'Copy Text';
                    btnCopyExtracted.classList.remove('btn-success');
                    btnCopyExtracted.classList.add('btn-outline');
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy to clipboard:', err);
            });
        });
    }

    // =========================================================
    // Helper: Button Loading State
    // =========================================================
    function setButtonLoading(button, isLoading) {
        if (!button) return;
        const textSpan = button.querySelector('.btn-text');
        const spinner = button.querySelector('.spinner');

        if (isLoading) {
            button.disabled = true;
            if (textSpan) textSpan.style.opacity = '0.4';
            if (spinner) spinner.style.display = 'inline-block';
        } else {
            button.disabled = false;
            if (textSpan) textSpan.style.opacity = '1';
            if (spinner) spinner.style.display = 'none';
        }
    }
});
