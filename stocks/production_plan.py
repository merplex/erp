"""O5 แผนงานผลิต — หน้าเดี่ยว (นอก Django admin) ลากใบสั่งผลิตลงเครื่องจักรรายวัน
- เวลาที่ใช้ = จำนวน x (เวลา / ผลผลิต) จาก O4, เครื่องละไม่เกินเวลาเต็มของวันนั้น (ค่าเริ่มต้น 24 ชม.)
- ลากแล้วเวลาไม่พอ -> ตัดจำนวนลงเท่าที่พอดีเวลา ที่เหลือค้างรอลงวัน/เครื่องอื่น
- ยอดรอวางแผน = จำนวนวางแผนของใบ - รวมที่ลงไว้ทุกวัน (แก้จำนวนวันในอดีต -> ยอดรอวางแผนเปลี่ยนตาม)
- วันที่ผ่านมาแล้วแก้ได้เมื่อปลดล็อก (allow_past)"""
import datetime
import json
from decimal import Decimal, ROUND_FLOOR, InvalidOperation

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (Machine, MachineDayCapacity, MachineProductCapacity, ProductionOrder, ProductionPlanSlot,
                     PLAN_ACTIVE_STATUSES, PLAN_DEFAULT_HOURS, plan_unit_hours)

STRIP_PAST_DAYS = 120     # แถบวันที่: ย้อนหลัง / ล่วงหน้า (เลื่อนซ้ายขวาดูได้)
STRIP_FUTURE_DAYS = 240


class PlanError(Exception):
    pass


def _num(value):
    text = f"{Decimal(value):,.2f}"
    return text.rstrip('0').rstrip('.')


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _day_capacity(machine, day):
    """เวลาเต็มของเครื่องในวันนั้น: แก้รายวันใน O5 > เวลาผลิตต่อวันใน O4 > 24 ชม."""
    row = MachineDayCapacity.objects.filter(machine_id=machine.pk, plan_date=day).first()
    return row.hours if row else machine.default_day_hours


def _used_hours(machine_id, day, exclude_slot_id=None):
    used = Decimal('0')
    slots = ProductionPlanSlot.objects.filter(machine_id=machine_id, plan_date=day).select_related('order', 'order__barcode_obj')
    if exclude_slot_id:
        slots = slots.exclude(pk=exclude_slot_id)
    for slot in slots:
        unit = plan_unit_hours(slot.order, machine_id)
        if unit is not None:
            used += slot.quantity * unit
    return used


def _unplanned(order, exclude_slot_id=None):
    qs = order.plan_slots.all()
    if exclude_slot_id:
        qs = qs.exclude(pk=exclude_slot_id)
    return order.quantity_planned - (qs.aggregate(s=Sum('quantity'))['s'] or 0)


def _fit_qty(free_hours, unit):
    if free_hours <= 0:
        return 0
    return int((free_hours / unit).to_integral_value(rounding=ROUND_FLOOR))


def _resequence(machine_id, day, slot, position):
    others = list(ProductionPlanSlot.objects.filter(machine_id=machine_id, plan_date=day).exclude(pk=slot.pk)
                  .order_by('sequence', 'id'))
    others.insert(max(0, min(position, len(others))), slot)
    for index, item in enumerate(others):
        item.sequence = index
    ProductionPlanSlot.objects.bulk_update(others, ['sequence'])


def _board(day):
    today = timezone.localdate()
    machines = list(Machine.objects.select_related('department').order_by('department__name', 'name'))
    day_slots = list(ProductionPlanSlot.objects.filter(plan_date=day)
                     .select_related('order', 'order__product', 'order__barcode_obj').order_by('sequence', 'id'))
    caps_by_machine = dict(MachineDayCapacity.objects.filter(plan_date=day).values_list('machine_id', 'hours'))

    active = list(ProductionOrder.objects.filter(status__in=PLAN_ACTIVE_STATUSES)
                  .select_related('product', 'barcode_obj').order_by('order_date', 'id'))
    orders = {o.pk: o for o in active}
    for slot in day_slots:
        orders.setdefault(slot.order_id, slot.order)
    planned_sum = dict(ProductionPlanSlot.objects.filter(order_id__in=list(orders))
                       .values('order_id').annotate(s=Sum('quantity')).values_list('order_id', 's'))

    capacities = list(MachineProductCapacity.objects.filter(product_id__in={o.product_id for o in orders.values()}))
    by_product = {}
    for cap in capacities:
        by_product.setdefault(cap.product_id, []).append(cap)

    def unit_for(order, machine_id):
        rows = [c for c in by_product.get(order.product_id, []) if c.machine_id == machine_id]
        exact = [c for c in rows if order.barcode_obj_id and c.barcode_obj_id == order.barcode_obj_id]
        cap = exact[0] if exact else next((c for c in rows if c.barcode_obj_id is None), None)
        return (cap.hours / cap.output_qty) if cap else None

    def base(order):
        return {
            'order_id': order.pk,
            'pd_number': order.pd_number,
            'product': order.product.name if order.product_id else '-',
            'barcode': order.barcode_obj.code if order.barcode_obj_id else '',
            'planned': order.quantity_planned,
            'unplanned': max(order.quantity_planned - (planned_sum.get(order.pk) or 0), 0),
            'status': order.get_status_display(),
            'order_date': order.order_date.strftime('%d/%m/%Y') if order.order_date else '',
            'url': f"/admin/stocks/productionorder/{order.pk}/change/",
        }

    def units_of(order):
        units = {}
        for m in machines:
            unit = unit_for(order, m.pk)
            if unit is not None:
                units[str(m.pk)] = float(unit)
        return units

    machine_rows = []
    for m in machines:
        slots, used = [], Decimal('0')
        for slot in (s for s in day_slots if s.machine_id == m.pk):
            unit = unit_for(slot.order, m.pk)
            hours = slot.quantity * unit if unit is not None else None
            used += hours or 0
            slots.append({**base(slot.order), 'id': slot.pk, 'qty': slot.quantity,
                          'hours': float(round(hours, 2)) if hours is not None else None,
                          'unit': float(unit) if unit is not None else None, 'units': units_of(slot.order)})
        machine_rows.append({
            'id': m.pk, 'name': m.name, 'type': m.machine_type,
            'department': m.department.name if m.department_id else '',
            'department_id': m.department_id,
            'capacity': float(caps_by_machine.get(m.pk, m.default_day_hours)),
            'default_capacity': float(m.default_day_hours),
            'used': float(round(used, 2)),
            'slots': slots,
        })

    pool = []
    for order in active:
        data = base(order)
        if data['unplanned'] <= 0:
            continue
        pool.append({**data, 'units': units_of(order)})

    start, end = today - datetime.timedelta(days=STRIP_PAST_DAYS), today + datetime.timedelta(days=STRIP_FUTURE_DAYS)
    plan_days = {d.isoformat(): n for d, n in ProductionPlanSlot.objects.filter(plan_date__range=(start, end))
                 .values('plan_date').annotate(n=Count('id')).values_list('plan_date', 'n')}
    return {
        'date': day.isoformat(),
        'today': today.isoformat(),
        'past': day < today,
        'default_hours': float(PLAN_DEFAULT_HOURS),
        'strip_start': start.isoformat(),
        'strip_end': end.isoformat(),
        'plan_days': plan_days,
        'machines': machine_rows,
        'pool': pool,
    }


@staff_member_required
def production_plan_view(request):
    return render(request, 'production_plan.html', {
        'can_change': request.user.has_perm('stocks.change_productionorder'),
    })


@staff_member_required
def production_plan_data(request):
    day = _parse_date(request.GET.get('date')) or timezone.localdate()
    return JsonResponse(_board(day))


def _place(body, day):
    order = (ProductionOrder.objects.select_for_update().select_related('product', 'barcode_obj')
             .filter(pk=int(body.get('order_id')), status__in=PLAN_ACTIVE_STATUSES).first())
    if not order:
        raise PlanError('ไม่พบใบสั่งผลิตนี้ หรือปิดงาน/ยกเลิกไปแล้ว')
    machine = Machine.objects.select_for_update().filter(pk=int(body.get('machine_id'))).first()
    if not machine:
        raise PlanError('ไม่พบเครื่องจักรนี้')
    unit = plan_unit_hours(order, machine.pk)
    if unit is None:
        raise PlanError(f"เครื่อง {machine.name} ยังไม่ได้ตั้งผลผลิตของ {order.product} (ตั้งได้ที่ O4 เครื่องจักร)")
    unplanned = _unplanned(order)
    if unplanned <= 0:
        raise PlanError(f"{order.pd_number} ลงแผนครบจำนวนแล้ว")
    capacity = _day_capacity(machine, day)
    free = capacity - _used_hours(machine.pk, day)
    qty = min(unplanned, _fit_qty(free, unit))
    if qty < 1:
        raise PlanError(f"เครื่อง {machine.name} วันนี้เวลาเต็มแล้ว ({_num(capacity)} ชม.)")
    slot = ProductionPlanSlot.objects.filter(order=order, machine=machine, plan_date=day).first()
    if slot:
        slot.quantity += qty
        slot.save(update_fields=['quantity'])
    else:
        slot = ProductionPlanSlot.objects.create(order=order, machine=machine, plan_date=day, quantity=qty)
    _resequence(machine.pk, day, slot, int(body.get('position') or 0))
    if qty < unplanned:
        return f"ลง {order.pd_number} ได้ {qty:,} จาก {unplanned:,} (เวลาเต็ม) เหลือ {unplanned - qty:,} ไปลงวัน/เครื่องอื่น"
    return f"ลง {order.pd_number} {qty:,} ชิ้น ({_num(qty * unit)} ชม.)"


def _move(body, slot):
    target = body.get('machine_id')
    position = int(body.get('position') or 0)
    if target in (None, ''):
        slot.delete()
        return f"เอา {slot.order.pd_number} ออกจากเครื่องแล้ว"
    machine = Machine.objects.select_for_update().filter(pk=int(target)).first()
    if not machine:
        raise PlanError('ไม่พบเครื่องจักรนี้')
    if machine.pk == slot.machine_id:
        _resequence(machine.pk, slot.plan_date, slot, position)
        return 'จัดลำดับแล้ว'
    unit = plan_unit_hours(slot.order, machine.pk)
    if unit is None:
        raise PlanError(f"เครื่อง {machine.name} ยังไม่ได้ตั้งผลผลิตของ {slot.order.product} (ตั้งได้ที่ O4 เครื่องจักร)")
    free = _day_capacity(machine, slot.plan_date) - _used_hours(machine.pk, slot.plan_date)
    qty = min(slot.quantity, _fit_qty(free, unit))
    if qty < 1:
        raise PlanError(f"เครื่อง {machine.name} วันนี้เวลาเต็มแล้ว")
    leftover = slot.quantity - qty
    existing = ProductionPlanSlot.objects.filter(order=slot.order, machine=machine, plan_date=slot.plan_date).first()
    if existing:
        existing.quantity += qty
        existing.save(update_fields=['quantity'])
        moved = existing
        slot.delete()
    else:
        slot.machine, slot.quantity = machine, qty
        slot.save(update_fields=['machine', 'quantity'])
        moved = slot
    _resequence(machine.pk, moved.plan_date, moved, position)
    if leftover:
        return f"ย้ายได้ {qty:,} (เวลาเต็ม) อีก {leftover:,} กลับไปรอลงเครื่อง"
    return f"ย้ายไป {machine.name} แล้ว"


def _set_qty(body, slot):
    try:
        qty = int(str(body.get('qty')).strip())
    except (TypeError, ValueError):
        raise PlanError('จำนวนต้องเป็นตัวเลขจำนวนเต็ม')
    if qty < 0:
        raise PlanError('จำนวนต้องไม่ติดลบ')
    if qty == 0:
        slot.delete()
        return f"เอา {slot.order.pd_number} ออกจากเครื่องแล้ว"
    asked = qty
    notes = []
    max_qty = slot.quantity + max(_unplanned(slot.order), 0)
    if qty > max_qty:
        qty = max_qty
        notes.append(f"ใบสั่งผลิตเหลือให้ลงได้ {max_qty:,}")
    unit = plan_unit_hours(slot.order, slot.machine_id)
    if unit is not None:
        capacity = _day_capacity(slot.machine, slot.plan_date)
        used = _used_hours(slot.machine_id, slot.plan_date, exclude_slot_id=slot.pk)
        fit = _fit_qty(capacity - used, unit)
        if qty > fit:
            qty = fit
            notes.append(f"เวลาว่าง {_num(max(capacity - used, 0))} ชม. ได้ {fit:,}")
    if qty < 1:
        raise PlanError('เครื่องนี้วันนี้เวลาเต็มแล้ว ใส่เพิ่มไม่ได้')
    slot.quantity = qty
    slot.save(update_fields=['quantity'])
    left = max(_unplanned(slot.order), 0)
    if qty < asked:
        return f"ใส่ {asked:,} ลงได้ {qty:,} ({', '.join(notes)}) — {slot.order.pd_number} รอลงเครื่องอีก {left:,}"
    return f"แก้จำนวนแล้ว — {slot.order.pd_number} รอลงเครื่องอีก {left:,}"


def _set_capacity(body, day):
    machine = Machine.objects.select_for_update().filter(pk=int(body.get('machine_id'))).first()
    if not machine:
        raise PlanError('ไม่พบเครื่องจักรนี้')
    try:
        hours = Decimal(str(body.get('hours')).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise PlanError('เวลาเต็มต้องเป็นตัวเลข')
    if not hours.is_finite() or hours < 0 or hours > 24:
        raise PlanError('เวลาเต็มต้องอยู่ระหว่าง 0 - 24 ชม.')
    hours = hours.quantize(Decimal('0.01'))
    used = _used_hours(machine.pk, day)
    if hours < used:
        raise PlanError(f"เครื่อง {machine.name} วันนี้ลงงานไว้แล้ว {_num(used)} ชม. ลดเวลาเต็มต่ำกว่านี้ไม่ได้")
    if hours == machine.default_day_hours:   # เท่าค่าเริ่มต้นของเครื่อง (O4) -> ไม่ต้องเก็บแถวรายวัน
        MachineDayCapacity.objects.filter(machine=machine, plan_date=day).delete()
    else:
        MachineDayCapacity.objects.update_or_create(machine=machine, plan_date=day, defaults={'hours': hours})
    return f"เวลาเต็ม {machine.name} = {_num(hours)} ชม."


@staff_member_required
@require_POST
def production_plan_action(request):
    """op: place (ลงใบจากกองรอ) / move (ย้าย/จัดลำดับ/เอาออก) / qty (แก้จำนวน) / capacity (เวลาเต็มของเครื่องในวัน)"""
    if not request.user.has_perm('stocks.change_productionorder'):
        return JsonResponse({'error': 'ไม่มีสิทธิ์แก้ไขใบสั่งผลิต'}, status=403)
    try:
        body = json.loads(request.body or b'{}')
        if not isinstance(body, dict):
            raise ValueError
    except ValueError:
        return JsonResponse({'error': 'ข้อมูลไม่ถูกต้อง'}, status=400)

    op = body.get('op')
    day = _parse_date(body.get('date')) or timezone.localdate()
    try:
        with transaction.atomic():
            slot = None
            if op in ('move', 'qty'):
                slot = (ProductionPlanSlot.objects.select_for_update()
                        .select_related('machine', 'order', 'order__product', 'order__barcode_obj')
                        .filter(pk=int(body.get('slot_id'))).first())
                if not slot:
                    raise PlanError('ไม่พบรายการนี้ (อาจถูกแก้จากที่อื่น) โหลดใหม่แล้วลองอีกครั้ง')
                day = slot.plan_date
            if day < timezone.localdate() and not body.get('allow_past'):
                raise PlanError('วันที่ผ่านมาแล้ว กดปลดล็อกก่อนจึงจะแก้ไขได้')
            if op == 'place':
                message = _place(body, day)
            elif op == 'move':
                message = _move(body, slot)
            elif op == 'qty':
                message = _set_qty(body, slot)
            elif op == 'capacity':
                message = _set_capacity(body, day)
            else:
                raise PlanError('ไม่รู้จักคำสั่งนี้')
    except PlanError as exc:
        return JsonResponse({'error': str(exc), 'board': _board(day)}, status=400)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'ข้อมูลไม่ถูกต้อง', 'board': _board(day)}, status=400)
    return JsonResponse({'ok': True, 'message': message, 'board': _board(day)})


THAI_MONTHS_SHORT = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
THAI_WEEKDAYS_SHORT = ['จ.', 'อ.', 'พ.', 'พฤ.', 'ศ.', 'ส.', 'อา.']


def _thai_date(day):
    return f"{THAI_WEEKDAYS_SHORT[day.weekday()]} {day.day} {THAI_MONTHS_SHORT[day.month - 1]} {day.year + 543}"


@staff_member_required
def production_plan_print(request):
    """ใบงานผลิต: งานที่ยังไม่เสร็จ (วันนี้เป็นต้นไป จนหมดแผน) ของเครื่อง (?machine=) หรือทั้งแผนก (?department= / none)
    ใบที่ลงหลายวันแสดงยอดแต่ละวัน, ท้ายใบโน้ตใบสั่งผลิตที่ยังลงเครื่องไม่ครบ (ที่เครื่องในใบนี้ผลิตได้)"""
    from django.http import Http404
    today = timezone.localdate()
    machine_id = (request.GET.get('machine') or '').strip()
    dept = (request.GET.get('department') or '').strip()
    machines = Machine.objects.select_related('department').order_by('machine_type', 'name')
    if machine_id.isdigit():
        machines = machines.filter(pk=int(machine_id))
        title_kind = 'เครื่องจักร'
    elif dept == 'none':
        machines = machines.filter(department__isnull=True)
        title_kind = 'แผนก'
    elif dept.isdigit():
        machines = machines.filter(department_id=int(dept))
        title_kind = 'แผนก'
    else:
        raise Http404('ระบุ machine หรือ department')
    machines = list(machines)
    if not machines:
        raise Http404('ไม่พบเครื่องจักร')
    if title_kind == 'เครื่องจักร':
        title = machines[0].name
    else:
        title = machines[0].department.name if machines[0].department_id else 'ไม่ระบุแผนก'

    slots = list(ProductionPlanSlot.objects.filter(machine__in=machines, plan_date__gte=today,
                                                   order__status__in=PLAN_ACTIVE_STATUSES)
                 .select_related('order', 'order__product', 'order__barcode_obj', 'machine')
                 .order_by('plan_date', 'sequence', 'id'))
    unit_cache = {}

    def unit(order, mid):
        key = (order.pk, mid)
        if key not in unit_cache:
            unit_cache[key] = plan_unit_hours(order, mid)
        return unit_cache[key]

    sections = []
    for m in machines:
        orders, total_hours = {}, Decimal('0')
        for slot in (s for s in slots if s.machine_id == m.pk):
            u = unit(slot.order, m.pk)
            hours = slot.quantity * u if u is not None else None
            row = orders.setdefault(slot.order_id, {'order': slot.order, 'days': [], 'qty': 0, 'hours': Decimal('0')})
            row['days'].append({'date': _thai_date(slot.plan_date), 'qty': f"{slot.quantity:,}",
                                'hours': _num(hours) if hours is not None else '-'})
            row['qty'] += slot.quantity
            row['hours'] += hours or 0
            total_hours += hours or 0
        rows = list(orders.values())
        for row in rows:
            row['hours'] = _num(row['hours'])
            row['qty'] = f"{row['qty']:,}"
            row['planned'] = f"{row['order'].quantity_planned:,}"
        sections.append({'machine': m, 'rows': rows, 'total_hours': _num(total_hours),
                         'last_date': _thai_date(max(s.plan_date for s in slots if s.machine_id == m.pk)) if rows else ''})

    # โน้ต: ใบสั่งผลิตที่ยังลงเครื่องไม่ครบ และเครื่องในใบนี้ผลิตได้
    planned_sum = dict(ProductionPlanSlot.objects.values('order_id').annotate(s=Sum('quantity')).values_list('order_id', 's'))
    pending = []
    for order in (ProductionOrder.objects.filter(status__in=PLAN_ACTIVE_STATUSES)
                  .select_related('product', 'barcode_obj').order_by('order_date', 'id')):
        left = order.quantity_planned - (planned_sum.get(order.pk) or 0)
        if left <= 0:
            continue
        able = [m.name for m in machines if unit(order, m.pk) is not None]
        if able:
            pending.append({'order': order, 'left': f"{left:,}", 'planned': f"{order.quantity_planned:,}",
                            'machines': ', '.join(able)})

    return render(request, 'production_plan_print.html', {
        'title': title, 'title_kind': title_kind, 'today': _thai_date(today),
        'printed_at': timezone.localtime().strftime('%d/%m/%Y %H:%M'),
        'sections': sections, 'pending': pending, 'single': title_kind == 'เครื่องจักร',
    })
