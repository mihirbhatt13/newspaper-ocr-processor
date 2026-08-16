document.addEventListener("DOMContentLoaded", () => {
  // State
  const state = {
    selectedFiles: [],
    inspectedFiles: [],
    eligibleFiles: [],
    duplicateFiles: [],
    processedResults: [],
    isProcessing: false,
    stopRequested: false,
  };

  // DOM Elements
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const fileStatsBar = document.getElementById("fileStatsBar");
  const selectedFilesCount = document.getElementById("selectedFilesCount");
  const btnClearFiles = document.getElementById("btnClearFiles");

  const targetDateInput = document.getElementById("targetDateInput");
  const ocrLanguageSelect = document.getElementById("ocrLanguageSelect");

  const btnCheckDuplicates = document.getElementById("btnCheckDuplicates");
  const btnStartOcr = document.getElementById("btnStartOcr");
  const btnStopOcr = document.getElementById("btnStopOcr");
  const btnCombine = document.getElementById("btnCombine");

  const progressSection = document.getElementById("progressSection");
  const lblStatus = document.getElementById("lblStatus");
  const pbarPdf = document.getElementById("pbarPdf");
  const pbarBatch = document.getElementById("pbarBatch");
  const pdfProgressText = document.getElementById("pdfProgressText");
  const batchProgressText = document.getElementById("batchProgressText");

  const reviewTableBody = document.getElementById("reviewTableBody");
  const duplicateTableBody = document.getElementById("duplicateTableBody");
  const queueCountBadge = document.getElementById("queueCountBadge");
  const duplicateCountBadge = document.getElementById("duplicateCountBadge");
  const engineStatusBadge = document.getElementById("engineStatusBadge");

  // Modal Elements
  const textModal = document.getElementById("textModal");
  const modalTitle = document.getElementById("modalTitle");
  const modalTextArea = document.getElementById("modalTextArea");
  const btnCloseModal = document.getElementById("btnCloseModal");
  const btnCloseModalFooter = document.getElementById("btnCloseModalFooter");
  const btnCopyText = document.getElementById("btnCopyText");
  const btnDownloadTxt = document.getElementById("btnDownloadTxt");

  let currentModalFilename = "combined_text.txt";

  // Check Engine Health on Load
  checkEngineHealth();

  async function checkEngineHealth() {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      if (data.tesseract_available) {
        engineStatusBadge.className = "status-badge status-online";
        engineStatusBadge.innerHTML = `🟢 Tesseract Engine Active (${data.installed_languages.length} Languages)`;
      } else {
        engineStatusBadge.className = "status-badge status-warning";
        engineStatusBadge.innerHTML = `🟡 Serverless Mode (Digital Text Stream Only)`;
      }
    } catch (e) {
      engineStatusBadge.className = "status-badge status-warning";
      engineStatusBadge.innerHTML = `⚠️ Engine Connection Warning`;
    }
  }

  // File Selection & Drag Drop
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length) {
      handleFiles(Array.from(e.target.files));
    }
  });

  btnClearFiles.addEventListener("click", () => {
    state.selectedFiles = [];
    state.inspectedFiles = [];
    state.eligibleFiles = [];
    state.duplicateFiles = [];
    state.processedResults = [];
    fileInput.value = "";
    fileStatsBar.style.display = "none";
    btnStartOcr.disabled = true;
    btnCombine.disabled = true;
    renderReviewTable();
    renderDuplicateTable();
    setStatus("Files cleared. Ready for input.");
  });

  async function handleFiles(files) {
    const pdfFiles = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfFiles.length) {
      alert("Please select valid PDF files.");
      return;
    }

    state.selectedFiles = pdfFiles;
    selectedFilesCount.textContent = `${pdfFiles.length} PDF File(s) Selected`;
    fileStatsBar.style.display = "flex";

    setStatus(`Inspecting ${pdfFiles.length} PDF file(s)...`);

    // Inspect files via API
    state.inspectedFiles = [];
    for (let i = 0; i < pdfFiles.length; i++) {
      const file = pdfFiles[i];
      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch("/api/inspect-pdf", { method: "POST", body: formData });
        const data = await res.json();
        if (data.success) {
          const info = data.info;
          info.fileObject = file;
          info.status = "PENDING";
          info.ocr_status = "PENDING";
          info.extractedText = "";
          state.inspectedFiles.push(info);
        }
      } catch (e) {
        console.error("Failed to inspect file:", file.name, e);
      }
    }

    state.eligibleFiles = [...state.inspectedFiles];
    state.duplicateFiles = [];
    renderReviewTable();
    renderDuplicateTable();
    setStatus(`Loaded ${state.inspectedFiles.length} PDF(s). Click "Check Duplicates" or "Start OCR Processing".`);
    btnStartOcr.disabled = false;
  }

  // Calculate SHA256 in browser
  async function calculateSha256(file) {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  // Check Duplicates Button
  btnCheckDuplicates.addEventListener("click", async () => {
    if (!state.inspectedFiles.length) {
      alert("Please upload PDF files first.");
      return;
    }

    setStatus("Running exact 4-Factor duplicate detection & target-date filter...");

    const payloadFiles = [];
    for (const f of state.inspectedFiles) {
      payloadFiles.push({
        filename: f.filename,
        file_size: f.file_size,
        sha256: f.sha256,
      });
    }

    try {
      const targetDate = targetDateInput.value;
      const res = await fetch("/api/check-duplicates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ files: payloadFiles, target_date: targetDate }),
      });

      const data = await res.json();
      if (data.success) {
        const eligibleList = data.result.eligible || [];
        const duplicateList = data.result.duplicates || [];

        const eligibleNames = new Set(eligibleList.map((e) => e.filename));

        state.eligibleFiles = state.inspectedFiles.filter((f) => eligibleNames.has(f.filename));
        state.duplicateFiles = duplicateList;

        renderReviewTable();
        renderDuplicateTable();

        setStatus(`Duplicate Check Complete: ${state.eligibleFiles.length} Eligible PDF(s), ${duplicateList.length} Duplicate/Out-of-date File(s).`);
        btnStartOcr.disabled = state.eligibleFiles.length === 0;
      }
    } catch (e) {
      alert("Duplicate check failed: " + e.message);
    }
  });

  // Start OCR Processing Button
  btnStartOcr.addEventListener("click", async () => {
    if (!state.eligibleFiles.length) {
      alert("No eligible PDF files to process.");
      return;
    }

    state.isProcessing = true;
    state.stopRequested = false;
    btnStartOcr.disabled = true;
    btnCheckDuplicates.disabled = true;
    btnStopOcr.disabled = false;
    btnCombine.disabled = true;
    state.processedResults = [];

    const selectedLang = ocrLanguageSelect.value;
    const totalFiles = state.eligibleFiles.length;

    for (let fIdx = 0; fIdx < totalFiles; fIdx++) {
      if (state.stopRequested) {
        setStatus("OCR Processing stopped by user.");
        break;
      }

      const fileInfo = state.eligibleFiles[fIdx];
      fileInfo.ocr_status = "PROCESSING...";
      renderReviewTable();

      updateBatchProgress(fIdx, totalFiles, `Processing ${fileInfo.filename} (${fIdx + 1}/${totalFiles})...`);

      const fileObj = fileInfo.fileObject;
      const pageCount = fileInfo.page_count || 1;
      let fullPdfText = "";
      let hasError = false;
      let errorMessage = "";

      for (let pNum = 1; pNum <= pageCount; pNum++) {
        if (state.stopRequested) break;

        updatePdfProgress(pNum, pageCount, `File ${fIdx + 1}/${totalFiles}: ${fileInfo.filename} - Page ${pNum}/${pageCount}`);

        const formData = new FormData();
        formData.append("file", fileObj);
        formData.append("page_num", pNum);
        formData.append("ocr_language", selectedLang);

        try {
          const res = await fetch("/api/process-page", { method: "POST", body: formData });
          const data = await res.json();

          if (data.success) {
            fullPdfText += `\n--- PAGE ${pNum} ---\n` + data.text;
          } else {
            hasError = true;
            errorMessage = data.message || "OCR Processing Error";
            if (data.ocr_error === "TESSERACT_UNAVAILABLE") {
              fileInfo.ocr_status = "ENGINE REQUIRED";
            } else {
              fileInfo.ocr_status = "FAILED";
            }
            break;
          }
        } catch (e) {
          hasError = true;
          errorMessage = e.message;
          fileInfo.ocr_status = "ERROR";
          break;
        }
      }

      if (!hasError && !state.stopRequested) {
        fileInfo.ocr_status = "COMPLETED";
        fileInfo.extractedText = fullPdfText.trim();
        state.processedResults.push({
          filename: fileInfo.filename,
          text: fileInfo.extractedText,
        });
      } else if (hasError) {
        fileInfo.extractedText = `[ERROR]: ${errorMessage}`;
      }

      updatePdfProgress(pageCount, pageCount, `Finished ${fileInfo.filename}`);
      renderReviewTable();
    }

    state.isProcessing = false;
    btnStartOcr.disabled = false;
    btnCheckDuplicates.disabled = false;
    btnStopOcr.disabled = true;

    if (state.processedResults.length > 0) {
      btnCombine.disabled = false;
      setStatus(`Batch Processing Complete! Processed ${state.processedResults.length} PDF(s). Click "COMBINE ALL TEXT" to view/download output.`);
    } else {
      setStatus("Processing finished with errors or no results.");
    }
  });

  // Stop Button
  btnStopOcr.addEventListener("click", () => {
    state.stopRequested = true;
    setStatus("Stopping processing...");
  });

  // Combine All Text Button
  btnCombine.addEventListener("click", async () => {
    if (!state.processedResults.length) {
      alert("No processed texts to combine.");
      return;
    }

    try {
      const res = await fetch("/api/combine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: state.processedResults }),
      });

      const data = await res.json();
      if (data.success) {
        showTextModal("Combined Newspaper Text Output (all_newspaper.txt)", data.combined_text, "all_newspaper.txt");
      }
    } catch (e) {
      alert("Combine failed: " + e.message);
    }
  });

  // Progress Helpers
  function setStatus(msg) {
    lblStatus.textContent = msg;
  }

  function updatePdfProgress(current, total, msg) {
    const pct = total > 0 ? Math.round((current / total) * 100) : 0;
    pbarPdf.style.width = `${pct}%`;
    pdfProgressText.textContent = `${current} / ${total} Pages (${pct}%)`;
    if (msg) setStatus(msg);
  }

  function updateBatchProgress(current, total, msg) {
    const pct = total > 0 ? Math.round((current / total) * 100) : 0;
    pbarBatch.style.width = `${pct}%`;
    batchProgressText.textContent = `${current} / ${total} PDFs (${pct}%)`;
    if (msg) setStatus(msg);
  }

  // Render Tables
  function renderReviewTable() {
    queueCountBadge.textContent = `${state.eligibleFiles.length} Items`;
    if (!state.eligibleFiles.length) {
      reviewTableBody.innerHTML = `<tr class="empty-row"><td colspan="9">No PDF files uploaded or eligible.</td></tr>`;
      return;
    }

    reviewTableBody.innerHTML = state.eligibleFiles
      .map((f, idx) => {
        let typeBadge = f.is_scanned ? `<span class="badge badge-warning">Scanned Image</span>` : `<span class="badge badge-info">Digital Text</span>`;
        let dupTag = `<span class="tag-unique">UNIQUE</span>`;
        
        let ocrTag = `<span class="tag-status-pending">${f.ocr_status || "PENDING"}</span>`;
        if (f.ocr_status === "COMPLETED") ocrTag = `<span class="tag-status-completed">COMPLETED</span>`;
        if (f.ocr_status === "ENGINE REQUIRED") ocrTag = `<span class="badge badge-warning">OCR Engine Required</span>`;
        if (f.ocr_status === "FAILED" || f.ocr_status === "ERROR") ocrTag = `<span class="tag-status-error">${f.ocr_status}</span>`;

        const txtLen = f.extractedText ? f.extractedText.length : 0;
        const btnView = f.extractedText
          ? `<button class="btn btn-sm btn-outline" onclick="window.viewFileText(${idx})">👁 View</button>`
          : `<button class="btn btn-sm btn-outline" disabled>👁 View</button>`;

        return `
          <tr>
            <td>${idx + 1}</td>
            <td><strong>${f.filename}</strong></td>
            <td>${f.iso_date || "DATE UNKNOWN"}</td>
            <td>${f.page_count}</td>
            <td>${typeBadge}</td>
            <td>${dupTag}</td>
            <td>${ocrTag}</td>
            <td>${txtLen} chars</td>
            <td>${btnView}</td>
          </tr>
        `;
      })
      .join("");
  }

  function renderDuplicateTable() {
    duplicateCountBadge.textContent = `${state.duplicateFiles.length} Duplicates`;
    if (!state.duplicateFiles.length) {
      duplicateTableBody.innerHTML = `<tr class="empty-row"><td colspan="5">No duplicate or out-of-date files detected.</td></tr>`;
      return;
    }

    duplicateTableBody.innerHTML = state.duplicateFiles
      .map((f) => {
        let reasonTag = f.status === "OUT-OF-DATE"
          ? `<span class="tag-out-of-date">${f.duplicate_of}</span>`
          : `<span class="tag-duplicate">Duplicate of ${f.duplicate_of}</span>`;

        return `
          <tr>
            <td><strong>${f.filename}</strong></td>
            <td>${f.newspaper_title || "-"}</td>
            <td>${f.iso_date || "DATE UNKNOWN"}</td>
            <td>${reasonTag}</td>
            <td><code>${(f.sha256 || "").substring(0, 16)}...</code></td>
          </tr>
        `;
      })
      .join("");
  }

  // Window helper for View button
  window.viewFileText = (idx) => {
    const item = state.eligibleFiles[idx];
    if (item && item.extractedText) {
      showTextModal(`Text Preview: ${item.filename}`, item.extractedText, `${item.filename}.txt`);
    }
  };

  // Modal Handlers
  function showTextModal(title, text, filename) {
    modalTitle.textContent = title;
    modalTextArea.value = text;
    currentModalFilename = filename;
    textModal.style.display = "flex";
  }

  function closeModal() {
    textModal.style.display = "none";
  }

  btnCloseModal.addEventListener("click", closeModal);
  btnCloseModalFooter.addEventListener("click", closeModal);

  btnCopyText.addEventListener("click", () => {
    navigator.clipboard.writeText(modalTextArea.value);
    alert("Text copied to clipboard!");
  });

  btnDownloadTxt.addEventListener("click", () => {
    const blob = new Blob([modalTextArea.value], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = currentModalFilename;
    a.click();
    URL.revokeObjectURL(url);
  });
});
