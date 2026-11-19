/**
 * DocuLedger PH — Zero-Login Recruiter Sandbox Client
 * Handles 1-click extraction, compliance audit, bounding-box overlays, and exports.
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    let activeDocId = null;
    let activeDocUrl = null;
    let currentBoundingBoxes = {};
    let currentDocType = 'SALES_INVOICE';

    // DOM Elements
    const sampleCards = document.querySelectorAll('.sample-card');
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const btnRunAudit = document.getElementById('btnRunAudit');
    const pdfIframe = document.getElementById('pdfIframe');
    const spatialOverlay = document.getElementById('spatialOverlay');
    const currentDocLabel = document.getElementById('currentDocLabel');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    // Scorecard Elements
    const scoreCircle = document.getElementById('scoreCircle');
    const scoreValue = document.getElementById('scoreValue');
    const overallStatusBadge = document.getElementById('overallStatusBadge');
    const detectedDocTypeBadge = document.getElementById('detectedDocTypeBadge');
    const auditSummaryText = document.getElementById('auditSummaryText');

    // Audit Tab Elements
    const auditRulesList = document.getElementById('auditRulesList');

    // Export Buttons
    const btnExportQuickBooks = document.getElementById('btnExportQuickBooks');
    const btnExportXero = document.getElementById('btnExportXero');
    const btnExportSLSP = document.getElementById('btnExportSLSP');

    // 1. Initialize Default Sample
    const firstActiveSample = document.querySelector('.sample-card.active');
    if (firstActiveSample) {
        selectSample(firstActiveSample);
    }

    // 2. Sample Card Click Listener
    sampleCards.forEach(card => {
        card.addEventListener('click', () => {
            sampleCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            selectSample(card);
        });
    });

    function selectSample(card) {
        activeDocId = card.getAttribute('data-id');
        activeDocUrl = card.getAttribute('data-url');
        const filename = card.getAttribute('data-filename');

        currentDocLabel.textContent = filename;
        if (pdfIframe && activeDocUrl) {
            pdfIframe.src = activeDocUrl;
        }

        // Reset export links
        updateExportLinks(activeDocId);
    }

    // 3. Tab Navigation
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const target = btn.getAttribute('data-tab');
            const panel = document.getElementById(target);
            if (panel) panel.classList.add('active');
        });
    });

    // 4. File Upload & Drag-and-Drop
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
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            uploadFile(fileInput.files[0]);
        }
    });

    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        btnRunAudit.disabled = true;
        btnRunAudit.querySelector('span').textContent = 'Uploading PDF...';

        try {
            const res = await fetch('/api/documents/upload/', {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) throw new Error('Upload failed');
            const data = await res.json();

            activeDocId = data.id;
            activeDocUrl = data.file_url;
            currentDocLabel.textContent = data.file_name;
            if (pdfIframe) pdfIframe.src = data.file_url;

            // Deselect sample cards
            sampleCards.forEach(c => c.classList.remove('active'));

            updateExportLinks(activeDocId);

            // Automatically trigger extract & audit on upload
            executeExtractAndAudit();
        } catch (err) {
            alert('Error uploading file: ' + err.message);
        } finally {
            btnRunAudit.disabled = false;
            btnRunAudit.querySelector('span').textContent = '1-Click Extract & Audit';
        }
    }

    // 5. 1-Click Extract & Audit Pipeline
    btnRunAudit.addEventListener('click', () => {
        executeExtractAndAudit();
    });

    async function executeExtractAndAudit() {
        if (!activeDocId) {
            alert('Please select a sample document or upload a PDF first.');
            return;
        }

        btnRunAudit.disabled = true;
        btnRunAudit.querySelector('span').textContent = 'Analyzing & Auditing...';

        try {
            const res = await fetch('/api/documents/extract-and-audit/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_id: activeDocId }),
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || 'Pipeline execution failed');
            }

            const data = await res.json();
            renderUnifiedResults(data);
        } catch (err) {
            alert('Audit Pipeline Error: ' + err.message);
        } finally {
            btnRunAudit.disabled = false;
            btnRunAudit.querySelector('span').textContent = '1-Click Extract & Audit';
        }
    }

    // 6. Render Unified Results
    function renderUnifiedResults(payload) {
        const doc = payload.document;
        const extraction = payload.extraction;
        const audit = payload.audit;
        const ledger = payload.ledger_entry;

        currentBoundingBoxes = extraction.bounding_boxes || {};
        currentDocType = extraction.document_type || 'SALES_INVOICE';

        // Update Scorecard
        renderScorecard(audit, currentDocType);

        // Update Audit Tab
        renderAuditRules(audit.results || []);

        // Update Extraction Tab
        renderExtractionFields(extraction.extracted_data || {});

        // Update Ledger & Journal Entry
        renderLedgerEntry(ledger, extraction.extracted_data || {});

        // Update Exporters
        updateExportLinks(doc.id);
    }

    function renderScorecard(audit, docType) {
        const score = audit.score !== undefined ? audit.score : 100;
        const status = audit.status || 'PASSED';
        const summary = audit.summary || '';

        scoreValue.textContent = score;

        // Circle color class
        scoreCircle.className = 'score-circle';
        if (status === 'PASSED') scoreCircle.classList.add('score-pass');
        else if (status === 'WARNING') scoreCircle.classList.add('score-warn');
        else scoreCircle.classList.add('score-fail');

        // Status badge
        overallStatusBadge.className = 'status-pill';
        if (status === 'PASSED') {
            overallStatusBadge.classList.add('status-pill-success');
            overallStatusBadge.textContent = '100% COMPLIANT';
        } else if (status === 'WARNING') {
            overallStatusBadge.classList.add('status-pill-warning');
            overallStatusBadge.textContent = 'WARNINGS DETECTED';
        } else {
            overallStatusBadge.classList.add('status-pill-danger');
            overallStatusBadge.textContent = 'AUDIT FAILED';
        }

        detectedDocTypeBadge.textContent = docType.replace('_', ' ');
        auditSummaryText.textContent = summary;
    }

    function renderAuditRules(results) {
        auditRulesList.innerHTML = '';
        if (results.length === 0) {
            auditRulesList.innerHTML = '<div class="empty-state"><p>No audit rules executed.</p></div>';
            return;
        }

        results.forEach(r => {
            const card = document.createElement('div');
            card.className = `rule-card ${
                r.status === 'PASS' ? 'rule-pass' :
                r.status === 'WARNING' ? 'rule-warning' : 'rule-fail'
            }`;

            const pillClass = r.status === 'PASS' ? 'status-pill-success' :
                              r.status === 'WARNING' ? 'status-pill-warning' : 'status-pill-danger';

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
                    <span class="status-pill ${pillClass}">${r.status}</span>
                </div>
                <div class="rule-msg">${r.message}</div>
                ${detailsHtml}
            `;
            auditRulesList.appendChild(card);
        });
    }

    function renderExtractionFields(data) {
        document.getElementById('fieldSupplierName').textContent = data.supplier_name || data.vendor_name || data.payee_name || '--';
        document.getElementById('fieldSupplierTIN').textContent = data.supplier_tin || data.vendor_tin || data.payee_tin || '--';
        document.getElementById('fieldSupplierAddress').textContent = data.supplier_address || 'Philippines';

        document.getElementById('fieldBuyerName').textContent = data.buyer_name || data.payor_name || '--';
        document.getElementById('fieldBuyerTIN').textContent = data.buyer_tin || data.payor_tin || '--';

        document.getElementById('fieldInvoiceNumber').textContent = data.invoice_number || data.po_number || data.atc_code || '--';
        document.getElementById('fieldInvoiceDate').textContent = data.invoice_date || data.po_date || '--';
        document.getElementById('fieldPORef').textContent = data.po_reference || '--';
        document.getElementById('fieldATPNumber').textContent = data.atp_number || 'N/A';

        // Line Items
        const tbody = document.getElementById('lineItemsBody');
        tbody.innerHTML = '';
        const items = data.line_items || [];
        if (items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No line items extracted.</td></tr>';
        } else {
            items.forEach(it => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${it.description}</td>
                    <td class="text-right">${parseFloat(it.quantity || 1).toFixed(2)}</td>
                    <td class="text-right">₱${parseFloat(it.unit_price || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                    <td class="text-right">₱${parseFloat(it.amount || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Totals
        const vatable = parseFloat(data.vatable_sales || data.income_payment || 0);
        const vat = parseFloat(data.vat_amount || data.tax_withheld || 0);
        const exempt = parseFloat(data.vat_exempt_sales || 0);
        const zero = parseFloat(data.zero_rated_sales || 0);
        const total = parseFloat(data.total_amount || 0);

        document.getElementById('fieldVatableSales').textContent = `PHP ${vatable.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
        document.getElementById('fieldVatAmount').textContent = `PHP ${vat.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
        document.getElementById('fieldVatExempt').textContent = `PHP ${exempt.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
        document.getElementById('fieldZeroRated').textContent = `PHP ${zero.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
        document.getElementById('fieldTotalAmount').textContent = `PHP ${total.toLocaleString('en-US', {minimumFractionDigits: 2})}`;

        setupBoundingBoxHighlights();
    }

    function renderLedgerEntry(ledger, extractedData) {
        const vatable = parseFloat(ledger ? ledger.vatable_sales : extractedData.vatable_sales || 0);
        const vat = parseFloat(ledger ? ledger.vat_amount : extractedData.vat_amount || 0);
        const total = parseFloat(ledger ? ledger.total_amount : extractedData.total_amount || 0);

        document.getElementById('journalDebitExpense').textContent = vatable.toLocaleString('en-US', {minimumFractionDigits: 2});
        document.getElementById('journalDebitVAT').textContent = vat.toLocaleString('en-US', {minimumFractionDigits: 2});
        document.getElementById('journalCreditAP').textContent = total.toLocaleString('en-US', {minimumFractionDigits: 2});

        const totalDebit = vatable + vat;
        document.getElementById('journalTotalDebit').textContent = totalDebit.toLocaleString('en-US', {minimumFractionDigits: 2});
        document.getElementById('journalTotalCredit').textContent = total.toLocaleString('en-US', {minimumFractionDigits: 2});
    }

    function updateExportLinks(docId) {
        if (!docId) return;
        btnExportQuickBooks.href = `/api/documents/${docId}/export/quickbooks/`;
        btnExportXero.href = `/api/documents/${docId}/export/xero/`;
        btnExportSLSP.href = `/api/documents/export/slsp/?document_id=${docId}`;
    }

    // 7. Interactive Bounding Box Highlights
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

        // Coordinates in PDF points (relative to 612 x 792 standard letter)
        const containerWidth = spatialOverlay.clientWidth || 500;
        const containerHeight = spatialOverlay.clientHeight || 650;

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
