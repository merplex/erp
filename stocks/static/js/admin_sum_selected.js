// static/js/admin_sum_selected.js
document.addEventListener('DOMContentLoaded', function() {
    const table = document.querySelector('#result_list');
    if (!table) return;

    // 1. สร้างกล่องแสดงผลแบบหลายบรรทัด
    const summaryBox = document.createElement('div');
    summaryBox.id = 'realtime-sum-box';
    summaryBox.style = 'display: inline-block; margin-left: 20px; padding: 8px 15px; background: #f0f4f8; border: 1px solid #d1d9e0; border-radius: 6px; font-size: 13px; vertical-align: middle;';
    summaryBox.innerHTML = '<span style="color: #666;">ติ๊กเลือกรายการเพื่อรวมยอด...</span>';
    
    const actionContainer = document.querySelector('.actions');
    if (actionContainer) actionContainer.appendChild(summaryBox);

    // 🎯 รายชื่อหัวตารางที่เปรมต้องการให้ระบบ "เฝ้าดู" (ใส่เพิ่มได้ไม่อั้น!)
    const targetLabels = [ 'สต็อกปัจจุบัน','แผนรับ (PO)','แผนส่ง (SO)','แผนผลิต (PD)','คาดการณ์ (PLAN)',   
        'รวมเงิน', 'รวมจ่าย', 'รวมยอด', 'กำไร', 'ยอดสุทธิ', 'GET BALANCE DUE LIST', 'ยอดสุทธิ (GRAND TOTAL)', 'GET BALANCE DUE DISPLAY', 'จำนวนขาย', 'ยอดขายรวม', 'ต้นทุนรวม (BUY)', 
        'กำไร (vs Buy)','จำนวน', 'INCL.VAT',  'EXCL.VAT', 'ยอดDC','ยอดREBATE', 'get_total_display'
    ];

    function calculateSum() {
        const headers = table.querySelectorAll('thead th');
        const activeColumns = [];

        // 🔍 สแกนหาว่าตารางนี้มีหัวข้อไหนตรงกับที่เราต้องการบ้าง
        headers.forEach((header, index) => {
            const headerText = header.innerText.trim();
            // เช็คว่าชื่อหัวตาราง ตรงกับลิสต์ที่เราตั้งไว้ไหม
            if (targetLabels.some(label => headerText.includes(label))) {
                activeColumns.push({
                    index: index,
                    label: headerText
                });
            }
        });

        const selectedRows = table.querySelectorAll('tbody tr.selected');
        
        if (selectedRows.length === 0 || activeColumns.length === 0) {
            summaryBox.innerHTML = '<span style="color: #666;">เลือกรายการเพื่อรวมยอด...</span>';
            return;
        }

        // 🧮 เริ่มคำนวณแยกตามคอลัมน์ที่เจอ
        const totals = {};
        activeColumns.forEach(col => totals[col.label] = 0);

        selectedRows.forEach(row => {
            const cells = row.querySelectorAll('td, th');
            activeColumns.forEach(col => {
                if (cells[col.index]) {
                    const valueText = cells[col.index].innerText.replace(/,/g, '').trim();
                    const value = parseFloat(valueText) || 0;
                    totals[col.label] += value;
                }
            });
        });

        // 📝 สร้างข้อความแสดงผล (แยกบรรทัดตามชื่อหัวข้อ)
        let displayText = `<div style="color: #333; margin-bottom: 3px;">บรรทัดที่เลือก: <b>${selectedRows.length}</b> รายการ</div>`;
        displayText += '<div style="display: grid; grid-template-columns: auto auto; gap: 5px 15px;">';
        
        for (const [label, sum] of Object.entries(totals)) {
            displayText += `
                <span style="color: #555;">${label}:</span>
                <b style="color: #2c3e50; text-align: right;">${sum.toLocaleString(undefined, {minimumFractionDigits: 2})}</b>
            `;
        }
        displayText += '</div>';
        
        summaryBox.innerHTML = displayText;
    }

    // ดักฟังการคลิก Checkbox (เหมือนเดิม)
    table.addEventListener('change', function(e) {
        if (e.target.classList.contains('action-select') || e.target.id === 'action-toggle') {
            setTimeout(calculateSum, 50);
        }
    });
});