-- ============================================================
-- Backfill dc_amount/rebate_amount สำหรับใบส่งของเก่าที่ยังไม่ confirm
-- (เทียบเท่า Django logic ใน SalesDeliveryLog.sync_dc_rebate_from_contract()
--  และคำสั่ง `python manage.py recalc_dc_rebate`)
--
-- ตั้งแต่ commit ที่เพิ่ม signal recalc_dc_rebate_on_contract_change ใน
-- stocks/models.py แล้ว การแก้ไข T2 (CustomerProductContract) ผ่านหน้าเว็บ
-- ปกติจะ trigger คำนวณใหม่อัตโนมัติทันที — คำสั่งชุดนี้จำเป็นเฉพาะ "ข้อมูลเก่า"
-- ที่มีอยู่ก่อน signal จะ deploy เท่านั้น (หรือกรณี import ข้อมูลเก่าเพิ่มทีหลัง
-- โดยไม่ผ่าน Django ORM เช่น import ตรงเข้า DB)
--
-- รันบน Railway Postgres console (เข้า `psql` ก่อน แล้ว paste ทีละคำสั่ง
-- เป็นบรรทัดเดียว — Railway console แบบ multi-line paste มักตัดไม่ครบ):
-- 1) รัน SELECT preview ก่อน ดูว่าจะเปลี่ยนกี่แถว/ค่าอะไรบ้าง
-- 2) ถ้าโอเค ค่อยรัน UPDATE จริง (ปลอดภัย รันซ้ำได้เรื่อยๆ - idempotent)
-- ============================================================

-- 1) PREVIEW (บรรทัดเดียว, copy วางได้เลย): แถวที่ค่าจะเปลี่ยนจริง (ยังไม่แก้อะไร)
-- SELECT * FROM ( SELECT sdl.id, so.so_number, sdl.product_id, sdl.is_dc_confirmed, sdl.is_rebate_confirmed, sdl.dc_amount AS old_dc, sdl.rebate_amount AS old_rebate, CASE WHEN sdl.is_dc_confirmed THEN sdl.dc_amount ELSE ROUND(sdl.shipment_value * COALESCE(cm.dc_percent, 0) / 100, 2) END AS new_dc, CASE WHEN sdl.is_rebate_confirmed THEN sdl.rebate_amount ELSE ROUND(sdl.shipment_value * COALESCE(cm.rebate_percent, 0) / 100, 2) END AS new_rebate FROM stocks_salesdeliverylog sdl JOIN stocks_salesorder so ON so.id = sdl.sales_order_id LEFT JOIN LATERAL ( SELECT c.dc_percent, c.rebate_percent FROM stocks_customerproductcontract c WHERE c.customer_id = so.customer_id AND c.product_id = sdl.product_id ORDER BY c.id LIMIT 1 ) cm ON true WHERE sdl.is_dc_confirmed = false OR sdl.is_rebate_confirmed = false ) diff WHERE new_dc <> old_dc OR new_rebate <> old_rebate ORDER BY id;

-- 2) UPDATE จริง (บรรทัดเดียว, copy วางได้เลย)
-- UPDATE stocks_salesdeliverylog AS sdl SET dc_amount = CASE WHEN sdl.is_dc_confirmed THEN sdl.dc_amount ELSE ROUND(sdl.shipment_value * COALESCE(cm.dc_percent, 0) / 100, 2) END, rebate_amount = CASE WHEN sdl.is_rebate_confirmed THEN sdl.rebate_amount ELSE ROUND(sdl.shipment_value * COALESCE(cm.rebate_percent, 0) / 100, 2) END FROM stocks_salesorder so LEFT JOIN LATERAL ( SELECT c.dc_percent, c.rebate_percent FROM stocks_customerproductcontract c WHERE c.customer_id = so.customer_id AND c.product_id = sdl.product_id ORDER BY c.id LIMIT 1 ) cm ON true WHERE sdl.sales_order_id = so.id AND (sdl.is_dc_confirmed = false OR sdl.is_rebate_confirmed = false);

-- ============================================================
-- เวอร์ชันจัดบรรทัดอ่านง่าย (เนื้อหาเดียวกับด้านบนทุกตัวอักษร แค่จัดย่อหน้า)
-- ============================================================

-- 1) PREVIEW
SELECT * FROM (
  SELECT
    sdl.id,
    so.so_number,
    sdl.product_id,
    sdl.is_dc_confirmed,
    sdl.is_rebate_confirmed,
    sdl.dc_amount     AS old_dc,
    sdl.rebate_amount AS old_rebate,
    CASE WHEN sdl.is_dc_confirmed THEN sdl.dc_amount
         ELSE ROUND(sdl.shipment_value * COALESCE(cm.dc_percent, 0) / 100, 2) END AS new_dc,
    CASE WHEN sdl.is_rebate_confirmed THEN sdl.rebate_amount
         ELSE ROUND(sdl.shipment_value * COALESCE(cm.rebate_percent, 0) / 100, 2) END AS new_rebate
  FROM stocks_salesdeliverylog sdl
  JOIN stocks_salesorder so ON so.id = sdl.sales_order_id
  LEFT JOIN LATERAL (
    SELECT c.dc_percent, c.rebate_percent
    FROM stocks_customerproductcontract c
    WHERE c.customer_id = so.customer_id AND c.product_id = sdl.product_id
    ORDER BY c.id
    LIMIT 1
  ) cm ON true
  WHERE sdl.is_dc_confirmed = false OR sdl.is_rebate_confirmed = false
) diff
WHERE new_dc <> old_dc OR new_rebate <> old_rebate
ORDER BY id;


-- 2) UPDATE จริง: รันเฉพาะตอนดู preview ข้างบนแล้วโอเคแล้วเท่านั้น
UPDATE stocks_salesdeliverylog AS sdl
SET
  dc_amount = CASE WHEN sdl.is_dc_confirmed THEN sdl.dc_amount
                   ELSE ROUND(sdl.shipment_value * COALESCE(cm.dc_percent, 0) / 100, 2) END,
  rebate_amount = CASE WHEN sdl.is_rebate_confirmed THEN sdl.rebate_amount
                       ELSE ROUND(sdl.shipment_value * COALESCE(cm.rebate_percent, 0) / 100, 2) END
FROM stocks_salesorder so
LEFT JOIN LATERAL (
  SELECT c.dc_percent, c.rebate_percent
  FROM stocks_customerproductcontract c
  WHERE c.customer_id = so.customer_id AND c.product_id = sdl.product_id
  ORDER BY c.id
  LIMIT 1
) cm ON true
WHERE sdl.sales_order_id = so.id
  AND (sdl.is_dc_confirmed = false OR sdl.is_rebate_confirmed = false);
