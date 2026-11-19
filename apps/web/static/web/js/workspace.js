/**
 * ProcuLedger Studio — Enterprise Document-to-Ledger & Compliance Client
 * Engineered for instant feedback, precision spatial coordinate mapping, and zero-latency audits.
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    let activeDocId = null;
    let activeDocUrl = null;
    let currentBoundingBoxes = {};
    let currentDocType = 'SALES_INVOICE';

    // DOM References
    const sampleCards = document.querySelectorAll('.sample-card');
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const btnRunAudit = document.getElementById('btnRunAudit');
    const btnHeaderUpload = document.getElementById('btnHeaderUpload');
    const pdfIframe = document.getElementById('pdfIframe');
    const spatialOverlay = document.getElementById('spatialOverlay');
    const currentDocLabel = document.getElementById('currentDocLabel');
    const viewerFileName = document.getElementById('viewerFileName');
    const btnOpenPdfNewTab = document.getElementById('btnOpenPdfNewTab');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');
    const mobileTabButtons = document.querySelectorAll('.mobile-tab-btn');

    // Scorecard Elements
    const scoreCircle = document.getElementById('scoreCircle');
    const scoreValue = document.getElementById('scoreValue');
    const overallStatusBadge = document.getElementById('overallStatusBadge');
    const detectedDocTypeBadge = document.getElementById('detectedDocTypeBadge');
    const auditSummaryText = document.getElementById('auditSummaryText');
    const mobileScoreBadge = document.getElementById('mobileScoreBadge');

    // Audit Tab Elements
    const auditRulesList = document.getElementById('auditRulesList');
    const rulesCountPill = document.getElementById('rulesCountPill');

    // Export Buttons
    const btnExportQuickBooks = document.getElementById('btnExportQuickBooks');
    const btnExportXero = document.getElementById('btnExportXero');
    const btnExportSLSP = document.getElementById('btnExportSLSP');

    // 1. Initialize Active Document from first sample
    const firstActiveSample = document.querySelector('.sample-card.active');
    if (firstActiveSample) {
        selectDocument(firstActiveSample);
    }

    // 2. Queue Item Selection
    sampleCards.forEach(card => {
        card.addEventListener('click', () => {
            sampleCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            selectDocument(card);
        });
    });

    function getPdfEmbedUrl(url) {
        if (!url) return '';
        const cleanUrl = url.split('#')[0];
        return `${cleanUrl}#toolbar=0&navpanes=0&view=FitH`;
    }

    function selectDocument(card) {
        activeDocId = card.getAttribute('data-id');
        activeDocUrl = card.getAttribute('data-url');
        const filename = card.getAttribute('data-filename');

        if (currentDocLabel) currentDocLabel.textContent = filename;
        if (viewerFileName) viewerFileName.textContent = filename;

        if (pdfIframe && activeDocUrl) {
            pdfIframe.src = getPdfEmbedUrl(activeDocUrl);
        }
        if (btnOpenPdfNewTab && activeDocUrl) {
            btnOpenPdfNewTab.href = activeDocUrl;
        }

        updateExportLinks(activeDocId);
    }

    // 3. Tab Navigation (Inspector)
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetId = btn.getAttribute('data-tab');
            const targetPanel = document.getElementById(targetId);
            if (targetPanel) targetPanel.classList.add('active');
        });
    });

    // 4. Mobile View Switcher
    if (mobileTabButtons.length > 0) {
        mobileTabButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                mobileTabButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const view = btn.getAttribute('data-view');
                const paneViewer = document.getElementById('paneViewer');
                const paneInspector = document.getElementById('paneInspector');
                const paneQueue = document.getElementById('paneQueue');

                if (window.innerWidth <= 900) {
                    if (view === 'viewer') {
                        if (paneViewer) paneViewer.scrollIntoView({ behavior: 'smooth' });
                    } else if (view === 'inspector') {
                        if (paneInspector) paneInspector.scrollIntoView({ behavior: 'smooth' });
                    } else if (view === 'queue') {
                        if (paneQueue) paneQueue.scrollIntoView({ behavior: 'smooth' });
                    }
                }
            });
        });
    }

    // 5. File Upload Triggers (Header button + Sidebar dropzone)
    if (btnHeaderUpload) {
        btnHeaderUpload.addEventListener('click', () => fileInput.click());
    }

    if (dropzone) {
        dropzone.addEventListener('click', () => fileInput.click());

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                uploadDocument(e.dataTransfer.files[0]);
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                uploadDocument(fileInput.files[0]);
            }
        });
    }

    async function uploadDocument(file) {
        const formData = new FormData();
        formData.append('file', file);

        setRunButtonLoading(true, 'Uploading Document...');

        try {
            const res = await fetch('/api/documents/upload/', {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) throw new Error('Document upload failed');
            const data = await res.json();

            activeDocId = data.id;
            activeDocUrl = data.file_url;

            if (currentDocLabel) currentDocLabel.textContent = data.file_name;
            if (viewerFileName) viewerFileName.textContent = data.file_name;
            if (pdfIframe) pdfIframe.src = getPdfEmbedUrl(data.file_url);
            if (btnOpenPdfNewTab) btnOpenPdfNewTab.href = data.file_url;

            // Deselect existing sample cards
            sampleCards.forEach(c => c.classList.remove('active'));

            updateExportLinks(activeDocId);

            // Automatically execute extraction and audit
            executeExtractAndAudit();
        } catch (err) {
            alert('Upload Error: ' + err.message);
        } finally {
            setRunButtonLoading(false);
        }
    }

    // 6. Action Button: 1-Click Extract & Audit
    if (btnRunAudit) {
        btnRunAudit.addEventListener('click', () => {
            executeExtractAndAudit();
        });
    }

    function setRunButtonLoading(isLoading, customText) {
        if (!btnRunAudit) return;
        btnRunAudit.disabled = isLoading;
        const textSpan = btnRunAudit.querySelector('span');
        if (textSpan) {
            textSpan.textContent = isLoading 
                ? (customText || 'Analyzing & Auditing...') 
                : '1-Click Extract & Audit';
        }
    }

    async function executeExtractAndAudit() {
        if (!activeDocId) {
            alert('Please select a document or upload a PDF first.');
            return;
        }

        setRunButtonLoading(true, 'Running Audit Engine...');

        try {
            const res = await fetch('/api/documents/extract-and-audit/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_id: activeDocId }),
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || 'Execution failed');
            }

            const data = await res.json();
            renderUnifiedResults(data);
        } catch (err) {
            alert('Audit Engine Error: ' + err.message);
        } finally {
            setRunButtonLoading(false);
        }
    }

    // 7. Render Unified Results
    function renderUnifiedResults(payload) {
        const doc = payload.document;
        const extraction = payload.extraction;
        const audit = payload.audit;
        const ledger = payload.ledger_entry;

        currentBoundingBoxes = extraction.bounding_boxes || {};
        currentDocType = extraction.document_type || 'SALES_INVOICE';

        renderScorecard(audit, currentDocType);
        renderAuditRules(audit.results || []);
        renderExtractionFields(extraction.extracted_data || {});
        renderLedgerEntry(ledger, extraction.extracted_data || {});
        updateExportLinks(doc.id);
    }

    function renderScorecard(audit, docType) {
        const score = audit.score !== undefined ? audit.score : 100;
        const status = audit.status || 'PASSED';
        const summary = audit.summary || '';

        if (scoreValue) scoreValue.textContent = score;
        if (mobileScoreBadge) mobileScoreBadge.textContent = score;

        if (scoreCircle) {
            scoreCircle.className = 'score-circle';
            if (status === 'PASSED') scoreCircle.classList.add('score-pass');
            else if (status === 'WARNING') scoreCircle.classList.add('score-warn');
            else scoreCircle.classList.add('score-fail');
        }

        if (overallStatusBadge) {
            overallStatusBadge.className = 'badge';
            if (status === 'PASSED') {
                overallStatusBadge.classList.add('badge-success');
                overallStatusBadge.innerHTML = '<span class="dot dot-success"></span> 100% COMPLIANT';
            } else if (status === 'WARNING') {
                overallStatusBadge.classList.add('badge-warning');
                overallStatusBadge.innerHTML = '<span class="dot dot-warning"></span> WARNINGS DETECTED';
            } else {
                overallStatusBadge.classList.add('badge-danger');
                overallStatusBadge.innerHTML = '<span class="dot dot-danger"></span> AUDIT FAILED';
            }
        }

        if (detectedDocTypeBadge) {
            detectedDocTypeBadge.textContent = docType.replace('_', ' ');
        }
        if (auditSummaryText) {
            auditSummaryText.textContent = summary;
        }
    }

    function renderAuditRules(results) {
        if (!auditRulesList) return;
        auditRulesList.innerHTML = '';

        if (rulesCountPill) {
            rulesCountPill.textContent = results.length;
        }

        if (results.length === 0) {
            auditRulesList.innerHTML = '<div class="empty-state-box"><p class="empty-title">No audit rules evaluated.</p></div>';
            return;
        }

        results.forEach(r => {
            const card = document.createElement('div');
            const isPass = r.status === 'PASS';
            const isWarn = r.status === 'WARNING';
            card.className = `rule-card ${isPass ? 'rule-pass' : isWarn ? 'rule-warning' : 'rule-fail'}`;

            const badgeClass = isPass ? 'badge-success' : isWarn ? 'badge-warning' : 'badge-danger';
            const dotClass = isPass ? 'dot-success' : isWarn ? 'dot-warning' : 'dot-danger';

            let detailsHtml = '';
            if (r.details && Object.keys(r.details).length > 0) {
                const kvPairs = Object.entries(r.details)
                    .map(([k, v]) => `<span>${k}: <strong>${v}</strong></span>`)
                    .join(' | ');
                detailsHtml = `<div class="rule-details-table">${kvPairs}</div>`;
            }

            card.innerHTML = `
                <div class="rule-card-header">
                    <span class="rule-title">${r.rule_name}</span>
                    <span class="badge ${badgeClass}">
                        <span class="dot ${dotClass}"></span> ${r.status}
                    </span>
                </div>
                <div class="rule-msg">${r.message}</div>
                ${detailsHtml}
            `;
            auditRulesList.appendChild(card);
        });
    }

    function renderExtractionFields(data) {
        setText('fieldSupplierName', data.supplier_name || data.vendor_name || data.payee_name || '--');
        setText('fieldSupplierTIN', data.supplier_tin || data.vendor_tin || data.payee_tin || '--');
        setText('fieldSupplierAddress', data.supplier_address || 'Philippines');

        setText('fieldBuyerName', data.buyer_name || data.payor_name || '--');
        setText('fieldBuyerTIN', data.buyer_tin || data.payor_tin || '--');

        setText('fieldInvoiceNumber', data.invoice_number || data.po_number || data.atc_code || '--');
        setText('fieldInvoiceDate', data.invoice_date || data.po_date || '--');
        setText('fieldPORef', data.po_reference || '--');
        setText('fieldATPNumber', data.atp_number || 'N/A');

        // Line Items Table
        const tbody = document.getElementById('lineItemsBody');
        if (tbody) {
            tbody.innerHTML = '';
            const items = data.line_items || [];
            if (items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="table-empty-cell">No line items extracted.</td></tr>';
            } else {
                items.forEach(it => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${it.description}</td>
                        <td class="col-num">${parseFloat(it.quantity || 1).toFixed(2)}</td>
                        <td class="col-num">₱${parseFloat(it.unit_price || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        <td class="col-num">₱${parseFloat(it.amount || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        }

        // Totals
        const vatable = parseFloat(data.vatable_sales || data.income_payment || 0);
        const vat = parseFloat(data.vat_amount || data.tax_withheld || 0);
        const exempt = parseFloat(data.vat_exempt_sales || 0);
        const zero = parseFloat(data.zero_rated_sales || 0);
        const total = parseFloat(data.total_amount || 0);

        setText('fieldVatableSales', `PHP ${vatable.toLocaleString('en-US', {minimumFractionDigits: 2})}`);
        setText('fieldVatAmount', `PHP ${vat.toLocaleString('en-US', {minimumFractionDigits: 2})}`);
        setText('fieldVatExempt', `PHP ${exempt.toLocaleString('en-US', {minimumFractionDigits: 2})}`);
        setText('fieldZeroRated', `PHP ${zero.toLocaleString('en-US', {minimumFractionDigits: 2})}`);
        setText('fieldTotalAmount', `PHP ${total.toLocaleString('en-US', {minimumFractionDigits: 2})}`);

        setupBoundingBoxHighlights();
    }

    function renderLedgerEntry(ledger, extractedData) {
        const vatable = parseFloat(ledger ? ledger.vatable_sales : extractedData.vatable_sales || 0);
        const vat = parseFloat(ledger ? ledger.vat_amount : extractedData.vat_amount || 0);
        const total = parseFloat(ledger ? ledger.total_amount : extractedData.total_amount || 0);

        setText('journalDebitExpense', vatable.toLocaleString('en-US', {minimumFractionDigits: 2}));
        setText('journalDebitVAT', vat.toLocaleString('en-US', {minimumFractionDigits: 2}));
        setText('journalCreditAP', total.toLocaleString('en-US', {minimumFractionDigits: 2}));

        const totalDebit = vatable + vat;
        setText('journalTotalDebit', totalDebit.toLocaleString('en-US', {minimumFractionDigits: 2}));
        setText('journalTotalCredit', total.toLocaleString('en-US', {minimumFractionDigits: 2}));
    }

    function updateExportLinks(docId) {
        if (!docId) return;
        if (btnExportQuickBooks) btnExportQuickBooks.href = `/api/documents/${docId}/export/quickbooks/`;
        if (btnExportXero) btnExportXero.href = `/api/documents/${docId}/export/xero/`;
        if (btnExportSLSP) btnExportSLSP.href = `/api/documents/export/slsp/?document_id=${docId}`;
    }

    function setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    // 8. Spatial Bounding Box Coordinate Mapping
    function setupBoundingBoxHighlights() {
        const highlightables = document.querySelectorAll('.highlightable');
        highlightables.forEach(el => {
            el.addEventListener('mouseenter', () => {
                const fieldKey = el.getAttribute('data-field');
                showBoundingBox(fieldKey);
            });
            el.addEventListener('mouseleave', () => {
                clearBoundingBox();
            });
        });
    }

    function showBoundingBox(fieldKey) {
        clearBoundingBox();
        const bbox = currentBoundingBoxes[fieldKey];
        if (!bbox || !spatialOverlay) return;

        const boxEl = document.createElement('div');
        boxEl.className = 'highlight-box';

        const containerWidth = spatialOverlay.clientWidth || 550;
        const containerHeight = spatialOverlay.clientHeight || 750;

        const scaleX = containerWidth / 612;
        const scaleY = containerHeight / 792;

        boxEl.style.left = `${bbox.x0 * scaleX}px`;
        boxEl.style.top = `${bbox.y0 * scaleY}px`;
        boxEl.style.width = `${Math.max(40, (bbox.x1 - bbox.x0) * scaleX)}px`;
        boxEl.style.height = `${Math.max(16, (bbox.y1 - bbox.y0) * scaleY)}px`;

        spatialOverlay.appendChild(boxEl);
    }

    function clearBoundingBox() {
        if (spatialOverlay) {
            spatialOverlay.innerHTML = '';
        }
    }
});
