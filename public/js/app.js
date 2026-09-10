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
  const folderInput = document.getElementById("folderInput");
  const btnSelectFolder = document.getElementById("btnSelectFolder");
  const btnSelectFiles = document.getElementById("btnSelectFiles");
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

  // File & Folder Selection Listeners
  if (btnSelectFolder) {
    btnSelectFolder.addEventListener("click", (e) => {
      e.stopPropagation();
      folderInput.click();
    });
  }

  if (btnSelectFiles) {
    btnSelectFiles.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  dropzone.addEventListener("click", (e) => {
    if (e.target.id === "btnSelectFolder" || e.target.id === "btnSelectFiles") return;
    if (folderInput) folderInput.click();
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));

  dropzone.addEventListener("drop", async (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    
    const items = e.dataTransfer.items;
    let extractedFiles = [];

    if (items && items.length) {
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === "file") {
          const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
          if (entry && entry.isDirectory) {
            const dirFiles = await scanDirectoryEntry(entry);
            extractedFiles.push(...dirFiles);
          } else {
            const file = item.getAsFile();
            if (file) extractedFiles.push(file);
          }
        }
      }
    } else if (e.dataTransfer.files.length) {
      extractedFiles = Array.from(e.dataTransfer.files);
    }

    if (extractedFiles.length) {
      handleFiles(extractedFiles, true);
    }
  });

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length) {
        handleFiles(Array.from(e.target.files), false);
      }
    });
  }

  if (folderInput) {
    folderInput.addEventListener("change", (e) => {
      if (e.target.files.length) {
        handleFiles(Array.from(e.target.files), true);
      }
    });
  }

  // Recursive Directory Scanner for Drag-and-Drop
  async function scanDirectoryEntry(dirEntry) {
    const files = [];
    const dirReader = dirEntry.createReader();
    
    const readEntriesPromise = () => new Promise((resolve) => dirReader.readEntries(resolve));
    
    let entries = await readEntriesPromise();
    while (entries.length > 0) {
      for (const entry of entries) {
        if (entry.isFile) {
          const file = await new Promise((resolve) => entry.file(resolve));
          files.push(file);
        } else if (entry.isDirectory) {
          const subFiles = await scanDirectoryEntry(entry);
          files.push(...subFiles);
        }
      }
      entries = await readEntriesPromise();
    }
    return files;
  }

  btnClearFiles.addEventListener("click", () => {
    state.selectedFiles = [];
    state.inspectedFiles = [];
    state.eligibleFiles = [];
    state.duplicateFiles = [];
    state.processedResults = [];
    if (fileInput) fileInput.value = "";
    if (folderInput) folderInput.value = "";
    fileStatsBar.style.display = "none";
    btnStartOcr.disabled = true;
    btnCombine.disabled = true;
    renderReviewTable();
    renderDuplicateTable();
    setStatus("Files cleared. Ready for input.");
  });

  function extractInfoFromFilename(filename) {
    let newspaperTitle = filename.replace(/\.pdf$/i, "").replace(/[0-9\-_.]/g, " ").trim() || "Newspaper";
    newspaperTitle = newspaperTitle.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");

    let isoDate = "";
    const match = filename.match(/(\d{1,2})[-_](\d{1,2})(?:[-_](\d{2,4}))?/);
    if (match) {
      const day = match[1].padStart(2, "0");
      const month = match[2].padStart(2, "0");
      let year = match[3] || "2026";
      if (year.length === 2) year = "20" + year;
      isoDate = `${year}-${month}-${day}`;
    }
    return { newspaperTitle, isoDate };
  }

  // Fetch with Retry Helper for Network Resilience
  async function fetchWithRetry(url, options, maxRetries = 2) {
    let attempt = 0;
    while (true) {
      try {
        const res = await fetch(url, options);
        if (!res.ok && attempt < maxRetries && res.status >= 500) {
          attempt++;
          await new Promise((r) => setTimeout(r, 500 * attempt));
          continue;
        }
        return res;
      } catch (err) {
        attempt++;
        if (attempt > maxRetries) throw err;
        await new Promise((r) => setTimeout(r, 500 * attempt));
      }
    }
  }

  // Fast Client-Side Real PDF Page-Count Detection (PDF.js -> Binary Parser -> API Fallback)
  async function detectPdfPageCount(file) {
    // 1. Try PDF.js if available in browser
    try {
      if (window.pdfjsLib) {
        pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
        const arrayBuffer = await file.arrayBuffer();
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        const pdfDoc = await loadingTask.promise;
        if (pdfDoc && pdfDoc.numPages > 0) {
          return pdfDoc.numPages;
        }
      }
    } catch (e) {
      console.warn("PDF.js page count failed for", file.name, e);
    }

    // 2. Try Binary TextDecoder structural inspection fallback
    try {
      const arrayBuffer = await file.arrayBuffer();
      const text = new TextDecoder("latin1").decode(new Uint8Array(arrayBuffer));
      
      const pageMatches = text.match(/\/Type\s*\/Page\b/g);
      if (pageMatches && pageMatches.length > 0) {
        return pageMatches.length;
      }
      
      const countMatch = text.match(/\/Count\s+(\d+)/);
      if (countMatch && parseInt(countMatch[1]) > 0) {
        return parseInt(countMatch[1]);
      }
    } catch (e) {
      console.warn("Binary PDF page count failed for", file.name, e);
    }

    // 3. Single-file API inspection fallback
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetchWithRetry("/api/inspect-pdf", { method: "POST", body: formData }, 1);
      const data = await res.json();
      if (data.success && data.info && data.info.page_count > 0) {
        return data.info.page_count;
      }
    } catch (e) {
      console.warn("Backend PDF page count inspect fallback failed for", file.name, e);
    }

    return 0; // Signals unreadable / invalid PDF structure
  }

  // Additional State for Batch Progress Tracking
  state.processedPagesCount = 0;
  state.totalPagesCount = 0;

  function updateLiveCounters() {
    const lblOverallPdfs = document.getElementById("lblOverallPdfs");
    const lblOverallPages = document.getElementById("lblOverallPages");
    const lblCurrentPdf = document.getElementById("lblCurrentPdf");
    const lblCurrentPage = document.getElementById("lblCurrentPage");
    const cntSuccess = document.getElementById("cntSuccess");
    const cntFailed = document.getElementById("cntFailed");
    const cntNeedsReview = document.getElementById("cntNeedsReview");
    const cntProcessing = document.getElementById("cntProcessing");
    const cntDuplicates = document.getElementById("cntDuplicates");
    const cntPending = document.getElementById("cntPending");
    const btnRetryFailed = document.getElementById("btnRetryFailed");

    let success = 0, failed = 0, needsReview = 0, processing = 0, pending = 0;

    state.eligibleFiles.forEach(f => {
      if (f.ocr_status === "SUCCESS" || f.ocr_status === "COMPLETED") success++;
      else if (f.ocr_status === "FAILED" || f.ocr_status === "ERROR") failed++;
      else if (f.ocr_status === "NEEDS REVIEW" || f.ocr_status === "ENGINE REQUIRED") needsReview++;
      else if (f.ocr_status === "PROCESSING...") processing++;
      else pending++;
    });

    const duplicates = state.duplicateFiles.length;
    const completedCount = success + failed + needsReview;

    if (lblOverallPdfs) lblOverallPdfs.textContent = `${completedCount} / ${state.eligibleFiles.length}`;
    if (lblOverallPages) lblOverallPages.textContent = `${state.processedPagesCount} / ${state.totalPagesCount}`;
    if (cntSuccess) cntSuccess.textContent = success;
    if (cntFailed) cntFailed.textContent = failed;
    if (cntNeedsReview) cntNeedsReview.textContent = needsReview;
    if (cntProcessing) cntProcessing.textContent = processing;
    if (cntDuplicates) cntDuplicates.textContent = duplicates;
    if (cntPending) cntPending.textContent = pending;

    if (btnRetryFailed) {
      if (failed > 0 || needsReview > 0) {
        btnRetryFailed.style.display = "inline-block";
        btnRetryFailed.disabled = state.isProcessing;
      } else {
        btnRetryFailed.style.display = "none";
        btnRetryFailed.disabled = true;
      }
    }
  }

  async function handleFiles(files, isFolderMode = false) {
    const pdfFiles = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    
    if (!pdfFiles.length) {
      alert("Unable to process the selected folder. Please check that it contains PDF files.");
      setStatus("Unable to process the selected folder. No PDF files found.");
      return;
    }

    state.selectedFiles = pdfFiles;
    
    // Detect folder name if available
    let folderName = "";
    if (pdfFiles[0] && pdfFiles[0].webkitRelativePath) {
      const parts = pdfFiles[0].webkitRelativePath.split("/");
      if (parts.length > 1) folderName = parts[0];
    }

    const labelText = folderName 
      ? `📁 ${pdfFiles.length} Newspaper PDFs found in folder '${folderName}'`
      : `📁 ${pdfFiles.length} Newspaper PDF File(s) Selected`;

    selectedFilesCount.textContent = labelText;
    fileStatsBar.style.display = "flex";

    // Load ALL detected PDF files instantly into the processing queue
    state.inspectedFiles = [];
    for (let i = 0; i < pdfFiles.length; i++) {
      const file = pdfFiles[i];
      const { newspaperTitle, isoDate } = extractInfoFromFilename(file.name);

      state.inspectedFiles.push({
        filename: file.name,
        file_size: file.size,
        newspaper_title: newspaperTitle,
        iso_date: isoDate,
        page_count: "Detecting...",
        is_scanned: true,
        fileObject: file,
        status: "PENDING",
        ocr_status: "PENDING",
        extractedText: ""
      });
    }

    state.eligibleFiles = [...state.inspectedFiles];
    state.duplicateFiles = [];
    state.processedResults = [];
    
    renderReviewTable();
    renderDuplicateTable();
    updateLiveCounters();

    setStatus(`Detected ${state.inspectedFiles.length} PDF(s) in queue. Calculating exact page counts...`);
    btnStartOcr.disabled = false;

    // Detect exact real page counts in controlled parallel batches of 5
    const batchSize = 5;
    for (let i = 0; i < pdfFiles.length; i += batchSize) {
      const chunk = pdfFiles.slice(i, i + batchSize);
      await Promise.all(chunk.map(async (file) => {
        const matchingItem = state.inspectedFiles.find(item => item.filename === file.name);
        if (matchingItem) {
          const realPageCount = await detectPdfPageCount(file);
          if (realPageCount > 0) {
            matchingItem.page_count = realPageCount;
          } else {
            matchingItem.page_count = 0;
            matchingItem.status = "NEEDS REVIEW";
            matchingItem.ocr_status = "NEEDS REVIEW";
            matchingItem.extractedText = "[ERROR]: Unreadable or corrupt PDF structure.";
          }
        }
      }));
      renderReviewTable();
      updateLiveCounters();
    }

    state.totalPagesCount = state.eligibleFiles.reduce((acc, f) => acc + (typeof f.page_count === "number" ? f.page_count : 0), 0);
    state.processedPagesCount = 0;
    updateLiveCounters();

    setStatus(`Detected ${state.inspectedFiles.length} PDF(s) in queue (${state.totalPagesCount} Total Pages). Click "Check Duplicates" or "Start OCR Processing".`);
  }

  // Calculate SHA256 in browser
  async function calculateSha256(file) {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  // Check Duplicates Button for ALL PDF files in batch
  btnCheckDuplicates.addEventListener("click", async () => {
    if (!state.inspectedFiles.length) {
      alert("Please upload PDF files first.");
      return;
    }

    setStatus("Calculating 4-Factor SHA-256 hashes for all selected PDFs...");

    const payloadFiles = [];
    for (const f of state.inspectedFiles) {
      if (!f.sha256) {
        f.sha256 = await calculateSha256(f.fileObject);
      }
      payloadFiles.push({
        filename: f.filename,
        file_size: f.file_size,
        sha256: f.sha256,
      });
    }

    setStatus("Running exact 4-Factor duplicate detection & target-date filter...");

    try {
      const targetDate = targetDateInput.value;
      const res = await fetchWithRetry("/api/check-duplicates", {
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

        state.totalPagesCount = state.eligibleFiles.reduce((acc, f) => acc + (typeof f.page_count === "number" ? f.page_count : 0), 0);

        renderReviewTable();
        renderDuplicateTable();
        updateLiveCounters();

        setStatus(`Duplicate Check Complete: ${state.eligibleFiles.length} Eligible PDF(s) (${state.totalPagesCount} Pages), ${duplicateList.length} Duplicate/Out-of-date File(s).`);
        btnStartOcr.disabled = state.eligibleFiles.length === 0;
      }
    } catch (e) {
      alert("Duplicate check failed: " + e.message);
    }
  });

  // Language Mapping Helper for Tesseract.js WASM Engine
  function mapLanguageForTesseractJs(langSetting) {
    const map = {
      "Auto": "hin+eng",
      "English": "eng",
      "Hindi": "hin",
      "Gujarati": "guj",
      "Marathi": "mar",
      "Bengali": "ben",
      "Telugu": "tel",
      "Urdu": "urd",
      "Hindi + English": "hin+eng",
      "Gujarati + English": "guj+eng",
      "Marathi + English": "mar+eng",
      "Bengali + English": "ben+eng",
      "Telugu + English": "tel+eng"
    };
    return map[langSetting] || "hin+eng";
  }

  // Render PDF Page to HTML5 Canvas in browser using PDF.js
  async function renderPdfPageToCanvas(pdfDoc, pageNum, dpi = 200) {
    const page = await pdfDoc.getPage(pageNum);
    const scale = dpi / 72.0;
    const viewport = page.getViewport({ scale });
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    canvas.height = viewport.height;
    canvas.width = viewport.width;

    await page.render({ canvasContext: context, viewport: viewport }).promise;
    return canvas;
  }

  // Hybrid Page Processor: Digital Text Stream -> Backend Serverless OCR -> Client-Side Tesseract.js WASM OCR
  async function processPageHybrid(fileObj, pdfDoc, pageNum, langSetting) {
    // 1. Digital Text Stream Extraction via PDF.js
    if (pdfDoc) {
      try {
        const page = await pdfDoc.getPage(pageNum);
        const textContent = await page.getTextContent();
        const extractedStreamText = textContent.items.map((item) => item.str).join(" ").trim();
        if (extractedStreamText.length >= 150) {
          return {
            success: true,
            text: extractedStreamText,
            engine_used: "PDF Text Stream"
          };
        }
      } catch (e) {
        console.warn("Digital text stream check failed for page", pageNum, e);
      }
    }

    // 2. Server Backend OCR API (/api/process-page)
    try {
      const formData = new FormData();
      formData.append("file", fileObj);
      formData.append("page_num", pageNum);
      formData.append("ocr_language", langSetting);

      const res = await fetchWithRetry("/api/process-page", { method: "POST", body: formData }, 1);
      const data = await res.json();
      if (data.success && data.text && data.text.trim().length > 0) {
        return {
          success: true,
          text: data.text,
          engine_used: data.engine_used || "Tesseract OCR (Server)"
        };
      } else if (data.ocr_error !== "TESSERACT_UNAVAILABLE" && data.text && data.text.trim().length > 0) {
        return {
          success: true,
          text: data.text,
          engine_used: "Text Stream (Server)"
        };
      }
    } catch (e) {
      console.warn("Backend OCR endpoint failed for page", pageNum, e);
    }

    // 3. Client-Side WebAssembly Tesseract.js Real OCR (Zero Server Dependencies)
    if (window.Tesseract && pdfDoc) {
      try {
        const canvas = await renderPdfPageToCanvas(pdfDoc, pageNum, 200);
        const tessLang = mapLanguageForTesseractJs(langSetting);
        const result = await Tesseract.recognize(canvas, tessLang);
        const ocrText = (result && result.data && result.data.text) ? result.data.text.trim() : "";
        
        return {
          success: true,
          text: ocrText,
          engine_used: `Tesseract.js WASM (${tessLang})`
        };
      } catch (wasmErr) {
        console.error("Tesseract.js WASM OCR failed for page", pageNum, wasmErr);
        return {
          success: false,
          ocr_error: "WASM_OCR_ERROR",
          message: `Browser WebAssembly OCR failed for page ${pageNum}: ${wasmErr.message || wasmErr}`
        };
      }
    }

    return {
      success: false,
      ocr_error: "NO_ENGINE_AVAILABLE",
      message: "No OCR engine available on server or browser for scanned newspaper page."
    };
  }

  // Start OCR Processing Button with Server-Side Batch Worker
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
    state.processedPagesCount = 0;
    state.totalPagesCount = state.eligibleFiles.reduce((acc, f) => acc + (typeof f.page_count === "number" ? f.page_count : 0), 0);

    const selectedLang = ocrLanguageSelect.value;
    const totalFiles = state.eligibleFiles.length;

    const lblOverallPdfs = document.getElementById("lblOverallPdfs");
    const lblCurrentPdf = document.getElementById("lblCurrentPdf");
    const lblCurrentPage = document.getElementById("lblCurrentPage");

    try {
      // 1. Create Server Batch Job
      setStatus("Initializing Server Batch Job...");
      const createRes = await fetchWithRetry("/api/batch/create", { method: "POST" }, 2);
      const createData = await createRes.json();
      
      if (!createData.success || !createData.job_id) {
        throw new Error(createData.error || "Failed to create server batch job");
      }
      const jobId = createData.job_id;

      // 2. Upload PDFs to Server Batch Storage (uploaded ONCE per PDF file)
      for (let i = 0; i < totalFiles; i++) {
        if (state.stopRequested) break;
        const fileInfo = state.eligibleFiles[i];
        setStatus(`Uploading file ${i + 1}/${totalFiles}: ${fileInfo.filename}...`);
        
        const formData = new FormData();
        formData.append("job_id", jobId);
        formData.append("file", fileInfo.fileObject);
        
        const upRes = await fetchWithRetry("/api/batch/upload-file", { method: "POST", body: formData }, 2);
        const upData = await upRes.json();
        if (!upData.success) {
          console.warn("Upload file warning:", fileInfo.filename, upData.error);
        }
      }

      if (state.stopRequested) {
        setStatus("Batch processing cancelled before start.");
        state.isProcessing = false;
        btnStartOcr.disabled = false;
        btnCheckDuplicates.disabled = false;
        btnStopOcr.disabled = true;
        return;
      }

      // 3. Start Server-Side Batch Processing Worker
      setStatus("Starting Server Batch Worker Engine...");
      await fetchWithRetry("/api/batch/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, ocr_language: selectedLang })
      }, 2);

      // 4. Poll Server Progress Loop
      while (state.isProcessing && !state.stopRequested) {
        const statusRes = await fetch(`/api/batch/status/${jobId}`);
        const statusResData = await statusRes.json();
        const sData = statusResData.status_data || {};

        if (sData.status) {
          state.processedPagesCount = sData.processed_pages || 0;
          state.totalPagesCount = sData.total_pages || state.totalPagesCount;
          
          if (lblCurrentPdf) lblCurrentPdf.textContent = sData.current_pdf || "Processing...";
          if (lblCurrentPage) lblCurrentPage.textContent = `Page ${sData.current_page || 1} / ${sData.total_pages || 1}`;

          updateBatchProgress(sData.completed_pdfs || 0, totalFiles);
          updatePdfProgress(sData.current_page || 1, sData.total_pages || 1, `Server OCR: ${sData.current_pdf} (Page ${sData.current_page})`);

          // Update table rows from server file statuses
          if (sData.files) {
            state.eligibleFiles.forEach(f => {
              const serverF = sData.files[f.filename];
              if (serverF) {
                f.ocr_status = serverF.status;
                if (serverF.extracted_text) {
                  f.extractedText = serverF.extracted_text;
                }
              }
            });
            renderReviewTable();
            updateLiveCounters();
          }

          if (sData.status === "COMPLETED") {
            break;
          }
        }
        await new Promise(r => setTimeout(r, 1000));
      }

      // 5. Retrieve Final Batch Result
      const resultRes = await fetch(`/api/batch/result/${jobId}`);
      const resultData = await resultRes.json();

      if (resultData.success) {
        state.processedResults = [];
        if (resultData.files) {
          Object.values(resultData.files).forEach(f => {
            if (f.extracted_text) {
              state.processedResults.push({
                filename: f.filename,
                text: f.extracted_text
              });
            }
          });
        }
      }

      if (state.processedResults.length > 0) {
        btnCombine.disabled = false;
        setStatus(`Server Batch Complete! Processed ${state.processedResults.length} of ${totalFiles} PDF(s) (${state.processedPagesCount} Pages). Click "COMBINE ALL TEXT" to view/download output.`);
      } else {
        setStatus("Processing finished with errors or no results.");
      }

    } catch (err) {
      console.error("Batch processing error:", err);
      setStatus(`Batch Processing Error: ${err.message}`);
    } finally {
      state.isProcessing = false;
      btnStartOcr.disabled = false;
      btnCheckDuplicates.disabled = false;
      btnStopOcr.disabled = true;
      if (lblCurrentPdf) lblCurrentPdf.textContent = state.stopRequested ? "Stopped" : "Batch Complete";
    }
  });

  // Retry Failed PDFs Button Event Listener
  const btnRetryFailed = document.getElementById("btnRetryFailed");
  if (btnRetryFailed) {
    btnRetryFailed.addEventListener("click", () => {
      let resetCount = 0;
      state.eligibleFiles.forEach(f => {
        if (f.ocr_status === "FAILED" || f.ocr_status === "NEEDS REVIEW" || f.ocr_status === "ENGINE REQUIRED" || f.ocr_status === "ERROR") {
          f.ocr_status = "PENDING";
          f.extractedText = "";
          resetCount++;
        }
      });
      if (resetCount > 0) {
        renderReviewTable();
        updateLiveCounters();
        setStatus(`Reset ${resetCount} failed/review PDF(s). Restarting OCR processing...`);
        btnStartOcr.click();
      }
    });
  }

  // Stop Button
  btnStopOcr.addEventListener("click", () => {
    state.stopRequested = true;
    setStatus("Stopping batch processing after current page...");
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
        if (f.ocr_status === "PROCESSING...") ocrTag = `<span class="badge" style="background:#2563eb; color:#fff;">PROCESSING...</span>`;
        if (f.ocr_status === "SUCCESS" || f.ocr_status === "COMPLETED") ocrTag = `<span class="tag-status-completed">SUCCESS</span>`;
        if (f.ocr_status === "ENGINE REQUIRED") ocrTag = `<span class="badge badge-warning">OCR Engine Required</span>`;
        if (f.ocr_status === "FAILED" || f.ocr_status === "ERROR") ocrTag = `<span class="tag-status-error">FAILED</span>`;
        if (f.ocr_status === "NEEDS REVIEW") ocrTag = `<span class="badge badge-info">NEEDS REVIEW</span>`;


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
