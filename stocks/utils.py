from decimal import Decimal, ROUND_HALF_UP

_THAI_DIGITS = ['', 'หนึ่ง', 'สอง', 'สาม', 'สี่', 'ห้า', 'หก', 'เจ็ด', 'แปด', 'เก้า']
_THAI_UNITS = ['', 'สิบ', 'ร้อย', 'พัน', 'หมื่น', 'แสน']


def _thai_read_int(number):
    """แปลงจำนวนเต็มไม่ติดลบเป็นคำอ่านภาษาไทย (ไม่มีหน่วยเงินต่อท้าย) รองรับหลักล้านซ้อนกันได้ไม่จำกัด"""
    if number == 0:
        return 'ศูนย์'

    digits = str(number)
    groups = []
    while digits:
        groups.insert(0, digits[-6:])
        digits = digits[:-6]

    parts = []
    num_groups = len(groups)
    for group_index, group in enumerate(groups):
        group = group.lstrip('0')
        if not group:
            continue
        group_len = len(group)
        group_text = ''
        for i, ch in enumerate(group):
            digit = int(ch)
            position = group_len - i - 1
            if digit == 0:
                continue
            if position == 0:
                group_text += 'เอ็ด' if (digit == 1 and group_len > 1) else _THAI_DIGITS[digit]
            elif position == 1:
                if digit == 1:
                    group_text += 'สิบ'
                elif digit == 2:
                    group_text += 'ยี่สิบ'
                else:
                    group_text += _THAI_DIGITS[digit] + 'สิบ'
            else:
                group_text += _THAI_DIGITS[digit] + _THAI_UNITS[position]
        million_power = num_groups - group_index - 1
        if million_power > 0:
            group_text += 'ล้าน' * million_power
        parts.append(group_text)
    return ''.join(parts)


def thai_baht_text(amount):
    """แปลงจำนวนเงินเป็นคำอ่านภาษาไทยแบบใบกำกับภาษี เช่น 2625651.60 -> 'สองล้านหกแสนสองหมื่นห้าพันหกร้อยห้าสิบเอ็ดบาทหกสิบสตางค์'"""
    amount = Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    negative = amount < 0
    amount = abs(amount)
    baht = int(amount)
    satang = int((amount - baht) * 100)

    text = _thai_read_int(baht) + 'บาท'
    if satang == 0:
        text += 'ถ้วน'
    else:
        text += _thai_read_int(satang) + 'สตางค์'
    if negative:
        text = 'ลบ' + text
    return text
