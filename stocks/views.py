import hashlib
import hmac
import json
import os
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from .models import DocumentLock
from . import line_webhook


def _report_token(report_type: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), report_type.encode(), hashlib.sha256).hexdigest()[:20]


def _webhook_handler(request, secret_env, token_env):
    if request.method != 'POST':
        return HttpResponse('ok')

    secret = os.environ.get(secret_env, '')
    token = os.environ.get(token_env, '')
    signature = request.headers.get('X-Line-Signature', '')
    body = request.body

    if not line_webhook.verify_signature(body, signature, secret):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning('LINE signature fail | secret_env=%s | secret_len=%d | sig=%s', secret_env, len(secret), signature[:20])
        return HttpResponse('invalid signature', status=403)

    try:
        data = json.loads(body)
        for event in data.get('events', []):
            line_webhook.handle_event(event, token)
    except Exception:
        pass

    return HttpResponse('ok')


@csrf_exempt
def line_webhook_view(request):
    """OA หลัก (ลูกค้า)"""
    return _webhook_handler(request, 'LINE_CHANNEL_SECRET', 'LINE_CHANNEL_ACCESS_TOKEN')


@csrf_exempt
def line_webhook2_view(request):
    """OA ส่วนตัว (Meebunholder Stock)"""
    return _webhook_handler(request, 'LINE2_CHANNEL_SECRET', 'LINE2_CHANNEL_ACCESS_TOKEN')


@staff_member_required
def delivery_log_autosave(request):
    """Auto-save delivery log row via AJAX — ผลลัพธ์เหมือนกด Save"""
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)

    from .models import ProductBarcode, SalesItem, SalesOrder, SalesDeliveryLog
    from django.utils import timezone as tz

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'invalid json'})

    so_id        = data.get('so_id')
    log_id       = data.get('log_id') or None
    barcode_code = (data.get('barcode_code') or '').strip()
    shipping_no  = (data.get('shipping_no') or '').strip()
    qty_raw      = data.get('quantity_shipped', '')
    notes        = (data.get('notes') or '').strip()
    shipped_date = (data.get('shipped_date') or '').strip()

    # validate SO
    try:
        so = SalesOrder.objects.get(pk=so_id)
    except (SalesOrder.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'ไม่พบ SO'})

    # validate barcode
    if not barcode_code:
        return JsonResponse({'success': False, 'error': 'กรุณากรอกรหัสบาร์โค้ด'})
    try:
        barcode = ProductBarcode.objects.select_related('product').get(code=barcode_code)
    except ProductBarcode.DoesNotExist:
        return JsonResponse({'success': False, 'errors': {'barcode_code': 'ไม่พบบาร์โค้ดนี้ ในใบสั่งขาย'}})
    if not SalesItem.objects.filter(sales_order=so, barcode_obj=barcode).exists():
        return JsonResponse({'success': False, 'errors': {'barcode_code': 'บาร์โค้ดนี้ไม่อยู่ในรายการสั่งขายนี้'}})

    # validate quantity
    try:
        qty = int(qty_raw)
        if qty < 0:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'errors': {'quantity_shipped': 'จำนวนต้องเป็นตัวเลขบวก'}})

    # parse shipped_date
    from django.utils.dateparse import parse_datetime, parse_date
    s_date = None
    if shipped_date:
        s_date = parse_datetime(shipped_date)
        if not s_date:
            d = parse_date(shipped_date)
            if d:
                s_date = tz.datetime(d.year, d.month, d.day, tzinfo=tz.get_current_timezone())
    if not s_date:
        s_date = tz.now()

    # get or create SalesDeliveryLog
    if log_id:
        try:
            log = SalesDeliveryLog.objects.get(pk=log_id, sales_order=so)
        except SalesDeliveryLog.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'ไม่พบ delivery log'})
        log.shipping_no     = shipping_no
        log.quantity_shipped = qty
        log.notes           = notes
        log.shipped_date    = s_date
        log.save()
    else:
        log = SalesDeliveryLog(
            sales_order      = so,
            barcode_obj      = barcode,
            shipping_no      = shipping_no,
            quantity_shipped = qty,
            notes            = notes,
            shipped_date     = s_date,
            user             = request.user,
        )
        log.save()  # model.save() จะ auto-set product + ลดสต็อก + อัพ quantity_shipped

    # คำนวณ remaining หลัง save (เป็นหน่วยบาร์โค้ด)
    from django.db.models import Sum
    factor = barcode.conversion_factor or 1
    items = SalesItem.objects.filter(sales_order=so, barcode_obj=barcode).values('quantity_ordered')
    total_ordered = sum(i['quantity_ordered'] or 0 for i in items)  # ชิ้น
    total_shipped_units = SalesDeliveryLog.objects.filter(
        sales_order=so, barcode_obj=barcode
    ).aggregate(total=Sum('quantity_shipped'))['total'] or 0
    remaining_pieces = max(0, total_ordered - total_shipped_units * factor)
    remaining = remaining_pieces // factor  # แสดงเป็นหน่วยบาร์โค้ด

    return JsonResponse({
        'success': True,
        'log_id': log.pk,
        'remaining': remaining,
        'unit_name': barcode.unit_name or 'ชิ้น',
        'barcode_code': barcode.code,
    })


@staff_member_required
def barcode_remaining_api(request):
    """API: ตรวจสอบ barcode code ว่าอยู่ใน SO ไหน และเหลือส่งเท่าไร"""
    from .models import ProductBarcode, SalesItem
    so_id = request.GET.get('so_id', '').strip()
    code = request.GET.get('barcode', '').strip()

    if not so_id or not code:
        return JsonResponse({'valid': False})

    try:
        barcode = ProductBarcode.objects.select_related('product').get(code=code)
    except ProductBarcode.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'ไม่พบบาร์โค้ดนี้ ในใบสั่งขาย'})

    from django.db.models import Sum
    from .models import SalesDeliveryLog
    items = list(SalesItem.objects.filter(sales_order_id=so_id, barcode_obj=barcode)
                 .values('quantity_ordered'))
    if not items:
        return JsonResponse({'valid': False, 'error': 'บาร์โค้ดนี้ไม่อยู่ในรายการสั่งขายนี้'})

    factor = barcode.conversion_factor or 1
    total_ordered = sum(i['quantity_ordered'] or 0 for i in items)  # เป็นชิ้น
    # quantity_shipped ใน log เป็นหน่วยบาร์โค้ด → แปลงเป็นชิ้นก่อนเทียบ
    total_shipped_units = SalesDeliveryLog.objects.filter(
        sales_order_id=so_id, barcode_obj=barcode
    ).aggregate(total=Sum('quantity_shipped'))['total'] or 0
    total_shipped_pieces = total_shipped_units * factor
    remaining_pieces = max(0, total_ordered - total_shipped_pieces)
    remaining = remaining_pieces // factor  # แสดงผลเป็นหน่วยบาร์โค้ด

    return JsonResponse({
        'valid': True,
        'remaining': remaining,
        'unit_name': barcode.unit_name or 'ชิ้น',
        'product_name': barcode.product.name if barcode.product else '',
    })


@staff_member_required
def pending_barcodes_api(request):
    """API: รายการบาร์โค้ดที่ยังส่งไม่ครบใน SO — แสดงใน pending bar"""
    from .models import ProductBarcode, SalesItem, SalesDeliveryLog, SalesOrder
    from django.db.models import Sum
    so_id = request.GET.get('so_id', '').strip()
    if not so_id:
        return JsonResponse({'items': []})
    try:
        so = SalesOrder.objects.get(pk=so_id)
    except (SalesOrder.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'items': []})

    items = SalesItem.objects.filter(sales_order=so).select_related('barcode_obj', 'product')
    result = []
    for item in items:
        if not item.barcode_obj:
            continue
        factor = item.barcode_obj.conversion_factor or 1
        ordered_pieces = item.quantity_ordered or 0  # ชิ้น
        shipped_units = SalesDeliveryLog.objects.filter(
            sales_order=so, barcode_obj=item.barcode_obj
        ).aggregate(total=Sum('quantity_shipped'))['total'] or 0
        remaining_pieces = max(0, ordered_pieces - shipped_units * factor)
        remaining = remaining_pieces // factor  # แสดงเป็นหน่วยบาร์โค้ด
        if remaining > 0:
            result.append({
                'barcode': item.barcode_obj.code,
                'product': item.product.name if item.product else '',
                'remaining': remaining,
                'unit_name': item.barcode_obj.unit_name or 'ชิ้น',
            })
    return JsonResponse({'items': result})


@staff_member_required
def barcode_info_api(request):
    """API: ดึงข้อมูล product + unit จาก barcode id — ใช้ใน contract autofill"""
    from .models import ProductBarcode
    barcode_id = request.GET.get('barcode_id', '').strip()
    if not barcode_id:
        return JsonResponse({})
    try:
        b = ProductBarcode.objects.select_related('product').get(pk=barcode_id)
    except (ProductBarcode.DoesNotExist, ValueError):
        return JsonResponse({})
    return JsonResponse({
        'product_id': b.product_id,
        'product_name': b.product.name if b.product else '',
        'unit_name': b.unit_name or 'ชิ้น',
        'conversion_factor': b.conversion_factor or 1,
    })


@staff_member_required
def contract_update_barcode_api(request):
    """API: อัปเดต barcode ของ CustomerProductContract แบบ AJAX (ไม่ reload หน้า)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)
    import json
    from .models import CustomerProductContract, ProductBarcode
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'invalid json'}, status=400)

    contract_id = data.get('contract_id')
    barcode_id = data.get('barcode_id')

    if not barcode_id:
        return JsonResponse({'error': 'barcode_id required'}, status=400)

    try:
        barcode = ProductBarcode.objects.select_related('product').get(pk=barcode_id)
    except (ProductBarcode.DoesNotExist, ValueError):
        return JsonResponse({'error': 'barcode not found'}, status=404)

    if contract_id:
        try:
            contract = CustomerProductContract.objects.get(pk=contract_id)
            contract.barcode = barcode
            contract.product = barcode.product
            contract.save(update_fields=['barcode', 'product'])
        except CustomerProductContract.DoesNotExist:
            pass  # contract ใหม่ที่ยังไม่ได้ save — แค่คืน info

    return JsonResponse({
        'product_name': barcode.product.name if barcode.product else '-',
        'unit_name': barcode.unit_name or 'ชิ้น',
        'conversion_factor': barcode.conversion_factor or 1,
    })


@csrf_exempt
def unlock_document_view(request):
    if request.method == 'POST' and request.user.is_authenticated:
        ct_id = request.POST.get('content_type_id')
        obj_id = request.POST.get('object_id')
        if ct_id and obj_id:
            DocumentLock.objects.filter(
                content_type_id=ct_id,
                object_id=str(obj_id),
                user=request.user
            ).delete()
    return HttpResponse('ok')


def stock_report_webview(request):
    """Webview สำหรับดูรายงานสต๊อกทั้งหมดใน LINE in-app browser"""
    from .models import Product
    from collections import defaultdict

    report_type = request.GET.get('type', 'cost')
    token = request.GET.get('token', '')

    expected = _report_token(report_type)
    if not hmac.compare_digest(token, expected):
        return HttpResponse('Unauthorized', status=401)

    # ─── Product / Package report (แยกตาม tag) ───────────────────────────────
    if report_type in ('product', 'package'):
        cat_name = 'Product' if report_type == 'product' else 'Packaging'
        with_sale = report_type == 'product'
        emoji = '📦' if report_type == 'product' else '📋'
        title = 'Product Report' if report_type == 'product' else 'Package Report'
        header_color = '#1a2e3a' if report_type == 'product' else '#2e2a1a'

        products = list(Product.objects.filter(
            is_product=True, category__name=cat_name
        ).prefetch_related('tags').order_by('name'))

        tag_groups = defaultdict(list)
        for p in products:
            tags = list(p.tags.all())
            if tags:
                for tg in tags:
                    tag_groups[tg.name].append(p)
            else:
                tag_groups['Non Tag'].append(p)

        def _tag_sort(k):
            return (1, k) if k == 'Non Tag' else (0, k)

        # 3 คอลัมน์: ชื่อสินค้า(จำนวน) | ต้นทุน฿ 2บรรทัด | ขาย฿ 2บรรทัด
        th_sale = '<th class="r" style="width:90px">ขาย ฿<br><span class="sub-hd">(ขาย/ชิ้น)</span></th>' if with_sale else ''

        rows_html = ''
        grand_cost = grand_sale = grand_stock = 0
        row_n = 0

        for tag_name in sorted(tag_groups.keys(), key=_tag_sort):
            tprods = sorted(tag_groups[tag_name], key=lambda p: p.name)
            t_cost = t_sale = t_stock = 0

            colspan = 3 if with_sale else 2
            rows_html += f'<tr><td colspan="{colspan}" class="tag-hd">▸ {tag_name} ({len(tprods)} รายการ)</td></tr>'

            for p in tprods:
                row_n += 1
                stock = int(p.stock_quantity or 0)
                buy = float(p.buy_price or 0)
                sale = float(p.sale_price or 0)
                cost_val = stock * buy
                sale_val = stock * sale
                t_stock += stock; t_cost += cost_val; t_sale += sale_val
                bg = '#fafafa' if row_n % 2 == 0 else '#ffffff'
                sale_td = f'<td class="r"><span class="val">{sale_val:,.0f}</span><br><span class="sub">({sale:,.2f})</span></td>' if with_sale else ''
                rows_html += (
                    f'<tr style="background:{bg}">'
                    f'<td class="nm">{p.name} <span class="qty">({stock:,})</span></td>'
                    f'<td class="r"><span class="val">{cost_val:,.0f}</span><br><span class="sub">({buy:,.2f})</span></td>'
                    f'{sale_td}'
                    f'</tr>'
                )

            grand_stock += t_stock; grand_cost += t_cost; grand_sale += t_sale
            sale_sub = f'<td class="r sub-row-td"><span class="val">{t_sale:,.0f}</span></td>' if with_sale else ''
            rows_html += (
                f'<tr class="sub-row">'
                f'<td class="nm">รวม {tag_name} ({t_stock:,} ชิ้น)</td>'
                f'<td class="r sub-row-td"><span class="val">{t_cost:,.0f}</span></td>'
                f'{sale_sub}'
                f'</tr>'
            )

        sale_foot = f'<span>ขาย {grand_sale:,.0f} ฿</span>' if with_sale else ''
        html = f'''<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>{emoji} {title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;background:#f5f5f5;color:#222}}
.hd{{background:{header_color};color:#fff;padding:10px 14px;position:sticky;top:0;z-index:10}}
.hd h1{{font-size:15px;font-weight:700}}
.hd p{{font-size:11px;color:#aaa;margin-top:2px}}
table{{width:100%;border-collapse:collapse;background:#fff}}
thead th{{background:#efefef;padding:7px 8px;font-size:11px;color:#777;position:sticky;top:46px;border-bottom:1px solid #ddd;line-height:1.4}}
th.l,td.nm{{text-align:left}}
th.r,td.r{{text-align:right}}
td{{padding:7px 8px;border-bottom:1px solid #f0f0f0;vertical-align:middle;line-height:1.5}}
td.nm{{word-break:break-word}}
.qty{{color:#aaa;font-size:11px}}
.val{{font-weight:700}}
.sub{{color:#999;font-size:10px}}
.sub-hd{{font-size:9px;color:#aaa;font-weight:400}}
.tag-hd{{background:#e8ecf0;font-weight:700;color:{header_color};padding:7px 8px;font-size:11px}}
.sub-row td{{background:#f0f4f8;border-top:1px solid #ccc;border-bottom:2px solid #bbb}}
.sub-row .nm{{font-weight:700;color:#444;font-size:11px}}
.sub-row-td .val{{color:#444}}
.ft{{background:{header_color};color:#fff;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;position:sticky;bottom:0;flex-wrap:wrap;gap:4px}}
.ft span{{font-size:11px;color:#ccc}}
.ft strong{{font-size:13px}}
</style>
</head>
<body>
<div class="hd"><h1>{emoji} {title}</h1><p>{len(products)} รายการ · เรียงชื่อในแต่ละ Tag</p></div>
<table>
<thead><tr>
<th class="l">ชื่อสินค้า (จำนวน)</th>
<th class="r" style="width:90px">ต้นทุน ฿<br><span class="sub-hd">(ทุน/ชิ้น)</span></th>
{th_sale}
</tr></thead>
<tbody>{rows_html}</tbody>
</table>
<div class="ft">
<span>ต้นทุน {grand_cost:,.0f} ฿</span>
{sale_foot}
<strong>สต๊อก {grand_stock:,} ชิ้น</strong>
</div>
</body>
</html>'''
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    # ─── Cost / Sale report (เรียงตามมูลค่า) ────────────────────────────────
    if report_type == 'cost':
        products = list(Product.objects.filter(is_product=True))
        products.sort(key=lambda p: float(p.stock_quantity or 0) * float(p.buy_price or 0), reverse=True)
        title = 'ต้นทุนสต๊อก'
        emoji = '💰'
        header_color = '#1a3a2e'
        col_label = 'ต้นทุน/ชิ้น'
        value_fn = lambda p: (float(p.stock_quantity or 0) * float(p.buy_price or 0), float(p.buy_price or 0))
        grand_label = 'รวมต้นทุน'
    else:
        products = list(Product.objects.filter(is_product=True))
        products.sort(key=lambda p: float(p.stock_quantity or 0) * float(p.sale_price or 0), reverse=True)
        title = 'มูลค่าสต๊อก'
        emoji = '💲'
        header_color = '#2e1a3a'
        col_label = 'ราคาขาย/ชิ้น'
        value_fn = lambda p: (float(p.stock_quantity or 0) * float(p.sale_price or 0), float(p.sale_price or 0))
        grand_label = 'รวมมูลค่า'

    grand_total = sum(value_fn(p)[0] for p in products)

    rows_html = ''
    for i, p in enumerate(products, 1):
        total_val, unit_price = value_fn(p)
        bg = '#fafafa' if i % 2 == 0 else '#ffffff'
        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td class="n">{i}</td>'
            f'<td class="nm">{p.name}</td>'
            f'<td class="r">{int(p.stock_quantity or 0):,}</td>'
            f'<td class="r">{unit_price:,.2f}</td>'
            f'<td class="r b">{total_val:,.0f}</td>'
            f'</tr>'
        )

    html = f'''<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>{emoji} {title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:12px;background:#f5f5f5;color:#222}}
.hd{{background:{header_color};color:#fff;padding:10px 14px;position:sticky;top:0;z-index:10}}
.hd h1{{font-size:15px;font-weight:700}}
.hd p{{font-size:11px;color:#aaa;margin-top:2px}}
table{{width:100%;border-collapse:collapse;background:#fff}}
thead th{{background:#efefef;padding:7px 5px;font-size:10px;color:#777;white-space:nowrap;position:sticky;top:46px;border-bottom:1px solid #ddd}}
th.l,td.nm{{text-align:left}}
th.r,td.r{{text-align:right}}
th.c,td.n{{text-align:center}}
td{{padding:6px 5px;border-bottom:1px solid #f0f0f0;vertical-align:middle}}
td.nm{{word-break:break-word;max-width:150px}}
td.n{{color:#aaa;font-size:11px}}
td.b{{font-weight:700}}
.ft{{background:{header_color};color:#fff;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;position:sticky;bottom:0}}
.ft span{{font-size:11px;color:#aaa}}
.ft strong{{font-size:14px}}
</style>
</head>
<body>
<div class="hd"><h1>{emoji} {title}</h1><p>{len(products)} รายการ · เรียงตามมูลค่ามากสุด</p></div>
<table>
<thead><tr>
<th class="c" style="width:30px">#</th>
<th class="l">ชื่อสินค้า</th>
<th class="r" style="width:48px">ชิ้น</th>
<th class="r" style="width:64px">{col_label}</th>
<th class="r" style="width:72px">มูลค่า ฿</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>
<div class="ft"><span>{grand_label}</span><strong>{grand_total:,.0f} ฿</strong></div>
</body>
</html>'''

    return HttpResponse(html, content_type='text/html; charset=utf-8')
