document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("uploadForm");
    const fileInput = document.getElementById("file");
    const dropzone = document.getElementById("dropzone");
    const previewBox = document.getElementById("filePreview");
    const previewName = document.getElementById("previewFileName");
    const previewSize = document.getElementById("previewFileSize");
    const previewHash = document.getElementById("previewFileHash");
    const uploadBtn = document.getElementById("uploadBtn");

    if (!form) return;

    // Helper to format file size
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Process file selection and compute SHA-256 live preview
    async function handleFileSelect(file) {
        if (!file) return;

        if (previewName) previewName.innerText = file.name;
        if (previewSize) previewSize.innerText = formatBytes(file.size);
        if (previewBox) previewBox.classList.add("active");
        if (previewHash) previewHash.innerText = "Computing SHA-256 cryptographic hash...";

        try {
            const hash = await calculateFileHash(file);
            if (previewHash) {
                previewHash.innerHTML = `${hash} <button type="button" class="copy-btn" onclick="copyToClipboard('${hash}', this)">📋</button>`;
            }
        } catch (e) {
            console.error("SHA-256 pre-calculation failed:", e);
            if (previewHash) previewHash.innerText = "Hash calculation pending upload...";
        }
    }

    if (fileInput) {
        fileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
            }
        });
    }

    if (dropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('dragover');
            }, false);
        });

        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                fileInput.files = files;
                handleFileSelect(files[0]);
            }
        });
    }

    form.addEventListener("submit", async function (e) {
        e.preventDefault();

        const caseid = document.getElementById("caseid").value.trim();
        const evidencename = document.getElementById("evidencename").value.trim();
        const file = fileInput ? fileInput.files[0] : null;

        if (!caseid || !evidencename || !file) {
            showToast("Please fill all fields and select an evidence file.", "error");
            return;
        }

        const formData = new FormData();
        formData.append("caseid", caseid);
        formData.append("evidencename", evidencename);
        formData.append("file", file);

        try {
            if (uploadBtn) {
                uploadBtn.disabled = true;
                uploadBtn.innerText = "⏳ Encrypting & Mining Blockchain Block...";
            }

            const response = await fetch("/upload", {
                method: "POST",
                body: formData
            });

            const result = await response.json();

            showToast(result.message, result.success ? "success" : "error");

            if (result.success) {
                setTimeout(() => {
                    window.location.href = "/evidence";
                }, 1200);
            } else {
                if (uploadBtn) {
                    uploadBtn.disabled = false;
                    uploadBtn.innerText = "🚀 Upload & Generate Blockchain Block";
                }
            }
        } catch (err) {
            console.error("Upload error:", err);
            showToast("Failed to upload evidence to server.", "error");
            if (uploadBtn) {
                uploadBtn.disabled = false;
                uploadBtn.innerText = "🚀 Upload & Generate Blockchain Block";
            }
        }
    });
});