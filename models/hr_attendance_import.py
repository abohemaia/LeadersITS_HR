import base64
import io
import logging
import re
from datetime import datetime, date, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MONTH_SELECTION = [
    ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'),
    ('4', 'أبريل'), ('5', 'مايو'), ('6', 'يونيو'),
    ('7', 'يوليو'), ('8', 'أغسطس'), ('9', 'سبتمبر'),
    ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
]

ATT_HEADER_MAP = {
    'كود البصمة': 'badge_code',
    'كود البصمه': 'badge_code',
    'رقم البصمة': 'badge_code',
    'رقم البصمه': 'badge_code',
    'الرقم البصمة': 'badge_code',
    'Badge': 'badge_code',
    'Badge ID': 'badge_code',
    'اسم الموظف': 'employee_name',
    'الاسم': 'employee_name',
    'تاريخ اليوم': 'day_date',
    'التاريخ': 'day_date',
    'تاريخ': 'day_date',
    'Date': 'day_date',
    'وقت الحركة': 'movement_time',
    'الوقت': 'movement_time',
    'وقت': 'movement_time',
    'Time': 'movement_time',
    'DateTime': 'movement_time',
    'الاتجاه': 'direction',
    'اتجاه': 'direction',
    'Direction': 'direction',
    'خط عرض': 'latitude',
    'Latitude': 'latitude',
    'خط طول': 'longitude',
    'Longitude': 'longitude',
}

VALID_DIRECTIONS = {'', 'in', 'out'}


def _normalize_ar(text):
    if not text:
        return ''
    text = str(text).strip()
    text = re.sub('[إأآا]', 'ا', text)
    text = re.sub('[ةه]$', 'ه', text)
    text = re.sub('[ً-ٟؐ-ؚٰ]', '', text)
    return text


def _parse_datetime(val):
    if not val:
        return False
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    val_str = str(val).strip()
    if not val_str:
        return False
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y %H:%M', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M',
                '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M',
                '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'):
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError:
            continue
    return False


def _parse_date(val):
    if not val:
        return False
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    val_str = str(val).strip()
    if not val_str:
        return False
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            continue
    return False


def _fix_month_swap(dt_obj, expected_month):
    """If dt_obj's month != expected_month, try swapping day and month."""
    if not dt_obj or not expected_month:
        return dt_obj, False
    exp_m = int(expected_month)
    if dt_obj.month == exp_m:
        return dt_obj, False
    if dt_obj.day <= 12:
        try:
            if isinstance(dt_obj, datetime):
                swapped = dt_obj.replace(month=dt_obj.day, day=dt_obj.month)
            else:
                swapped = dt_obj.replace(month=dt_obj.day, day=dt_obj.month)
            if swapped.month == exp_m:
                return swapped, True
        except ValueError:
            pass
    return dt_obj, False


class LeadersitsHrAttendanceImport(models.Model):
    _name = 'leadersits.hr.attendance.import'
    _description = 'سحب بيانات الحضور من اكسيل'
    _order = 'create_date desc'

    name = fields.Char(string="المرجع", readonly=True,
                       default=lambda self: _('New'))
    excel_file = fields.Binary(string="ملف الإكسيل", required=True)
    file_name = fields.Char(string="اسم الملف")
    expected_month = fields.Selection(MONTH_SELECTION,
                                      string="الشهر المتوقع", required=True)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('tested', 'تم الاختبار'),
        ('done', 'تم الإرسال'),
        ('error', 'خطأ'),
    ], string="الحالة", default='draft', readonly=True)
    log = fields.Text(string="نتيجة الاختبار", readonly=True)
    total_rows = fields.Integer(string="إجمالي السطور", readonly=True)
    valid_rows = fields.Integer(string="سطور صحيحة", readonly=True)
    error_rows = fields.Integer(string="سطور خاطئة", readonly=True)
    sent_count = fields.Integer(string="سجلات تم إرسالها", readonly=True)
    duplicate_count = fields.Integer(string="سجلات مكررة", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'leadersits.hr.attendance.import') or _('New')
        return super().create(vals_list)

    def _map_headers(self, headers):
        col_map = {}
        normalized = {}
        for ar_key, en_key in ATT_HEADER_MAP.items():
            normalized[_normalize_ar(ar_key)] = en_key

        for idx, header in enumerate(headers):
            if not header:
                continue
            h = str(header).strip()
            h_norm = _normalize_ar(h)
            if h in ATT_HEADER_MAP:
                col_map[ATT_HEADER_MAP[h]] = idx
                continue
            if h_norm in normalized:
                col_map[normalized[h_norm]] = idx
                continue
            for ar_norm, en_key in normalized.items():
                if en_key not in col_map and ar_norm in h_norm:
                    col_map[en_key] = idx
                    break
        return col_map

    def _read_excel(self):
        self.ensure_one()
        if not self.excel_file:
            raise UserError(_("يرجى رفع ملف إكسيل"))
        try:
            import openpyxl
        except ImportError:
            raise UserError(_(
                "مكتبة openpyxl غير متوفرة. يرجى تثبيتها: pip install openpyxl"))

        file_data = base64.b64decode(self.excel_file)
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_data), read_only=True)
        except Exception:
            raise UserError(_("الملف غير صالح. يرجى رفع ملف Excel (.xlsx)"))

        sheet = wb.active
        rows = list(sheet.iter_rows(values_only=True))
        wb.close()

        if len(rows) < 2:
            raise UserError(_("الملف لا يحتوي على بيانات"))

        col_map = self._map_headers(rows[0])
        if 'badge_code' not in col_map:
            detected = ", ".join(str(h).strip() for h in rows[0] if h)
            raise UserError(_(
                "لم يتم العثور على عمود 'كود البصمة'.\nالأعمدة: %s") % detected)
        if 'movement_time' not in col_map:
            detected = ", ".join(str(h).strip() for h in rows[0] if h)
            raise UserError(_(
                "لم يتم العثور على عمود 'وقت الحركة'.\nالأعمدة: %s") % detected)

        return rows[1:], col_map

    def _parse_row(self, row, col_map):
        def get(key):
            idx = col_map.get(key)
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        badge_raw = get('badge_code')
        if badge_raw is None:
            return None, "لا يوجد كود بصمة"
        badge = str(badge_raw).strip()
        if isinstance(badge_raw, float) and badge_raw == int(badge_raw):
            badge = str(int(badge_raw))
        if not badge:
            return None, "كود البصمة فارغ"

        mt_raw = get('movement_time')
        movement_dt = _parse_datetime(mt_raw)
        if not movement_dt:
            return None, f"وقت الحركة غير صالح: {mt_raw}"

        movement_dt, mt_swapped = _fix_month_swap(
            movement_dt, self.expected_month)

        dd_raw = get('day_date')
        if dd_raw:
            calc_d = _parse_date(dd_raw)
            if calc_d:
                calc_d, _ = _fix_month_swap(calc_d, self.expected_month)
                diff = abs((calc_d - movement_dt.date()).days)
                if diff > 1:
                    return None, (f"تاريخ اليوم {calc_d} لا يطابق وقت الحركة "
                                  f"{movement_dt.date()} (فرق {diff} يوم)")
            else:
                calc_d = movement_dt.date()
        else:
            calc_d = movement_dt.date()

        dir_raw = get('direction')
        direction = '--'
        if dir_raw:
            dir_str = str(dir_raw).strip().lower()
            if dir_str in ('in', 'حضور'):
                direction = 'in'
            elif dir_str in ('out', 'انصراف'):
                direction = 'out'

        lat = get('latitude')
        lng = get('longitude')
        try:
            lat = float(lat) if lat else 0.0
        except (ValueError, TypeError):
            lat = 0.0
        try:
            lng = float(lng) if lng else 0.0
        except (ValueError, TypeError):
            lng = 0.0

        return {
            'badge_code': badge,
            'calc_date': calc_d,
            'tr_dt': movement_dt,
            'direction': direction,
            'latitude': lat,
            'longitude': lng,
        }, None

    def action_test(self):
        self.ensure_one()
        rows, col_map = self._read_excel()

        log_lines = []
        log_lines.append("الأعمدة المكتشفة: " + ", ".join(col_map.keys()))

        emp_cache = {}
        Employee = self.env['hr.employee']

        valid = 0
        errors = 0
        skipped = 0
        no_employee = set()
        total = 0

        for row_idx, row in enumerate(rows, start=2):
            all_none = all(cell is None for cell in row)
            if all_none:
                continue
            total += 1

            parsed, err = self._parse_row(row, col_map)
            if err:
                errors += 1
                log_lines.append(f"سطر {row_idx}: {err}")
                continue

            badge = parsed['badge_code']
            if badge not in emp_cache:
                emp = Employee.search([('barcode', '=', badge)], limit=1)
                emp_cache[badge] = emp.id if emp else False

            if not emp_cache[badge]:
                if badge not in no_employee:
                    no_employee.add(badge)
                skipped += 1
                continue

            valid += 1

        if no_employee:
            log_lines.append("---")
            log_lines.append(
                f"أكواد بصمة غير موجودة ({len(no_employee)}): "
                + ", ".join(sorted(no_employee)))
            log_lines.append(
                f"سطور سيتم تخطيها (كود غير موجود): {skipped}")

        log_lines.append("---")
        log_lines.append(f"إجمالي السطور: {total}")
        log_lines.append(f"سطور صحيحة جاهزة للإرسال: {valid}")
        log_lines.append(f"سطور سيتم تخطيها: {skipped}")
        if errors:
            log_lines.append(f"سطور بها أخطاء: {errors}")

        new_state = 'tested' if valid > 0 else 'error'

        self.write({
            'state': new_state,
            'log': '\n'.join(log_lines),
            'total_rows': total,
            'valid_rows': valid,
            'error_rows': errors,
        })

    def action_send(self):
        self.ensure_one()
        if self.state != 'tested':
            raise UserError(_("يجب اختبار الملف أولاً والتأكد من صحة البيانات"))

        rows, col_map = self._read_excel()

        Employee = self.env['hr.employee']
        Detail = self.env['leadersits.hr.attendance.detail']
        emp_cache = {}
        tz_name = self.env.user.tz or self.env.company.tz or 'UTC'
        local_tz = pytz.timezone(tz_name)

        sent = 0
        duplicates = 0
        errors = 0
        log_lines = []

        for row_idx, row in enumerate(rows, start=2):
            all_none = all(cell is None for cell in row)
            if all_none:
                continue

            parsed, err = self._parse_row(row, col_map)
            if err:
                continue

            badge = parsed['badge_code']
            if badge not in emp_cache:
                emp = Employee.search([('barcode', '=', badge)], limit=1)
                emp_cache[badge] = emp.id if emp else False

            emp_id = emp_cache.get(badge)
            if not emp_id:
                continue

            tr_dt_local = parsed['tr_dt']
            tr_dt_utc = local_tz.localize(tr_dt_local).astimezone(
                pytz.utc).replace(tzinfo=None)

            existing = Detail.search([
                ('employee_id', '=', emp_id),
                ('tr_dt', '=', tr_dt_utc),
            ], limit=1)
            if existing:
                duplicates += 1
                continue

            vals = {
                'employee_id': emp_id,
                'calc_date': parsed['calc_date'],
                'tr_dt': tr_dt_utc,
                'direction': parsed['direction'],
                'tr_type': 'excel',
            }
            vals['latitude'] = parsed['latitude']
            vals['longitude'] = parsed['longitude']

            try:
                Detail.create(vals)
                sent += 1
            except Exception as e:
                if 'employee_trdt_unique' in str(e):
                    duplicates += 1
                else:
                    errors += 1
                    log_lines.append(f"سطر {row_idx}: خطأ - {e}")

        log_lines.append("---")
        log_lines.append(f"تم إرسال: {sent} سجل")
        log_lines.append(f"مكررات تم تخطيها: {duplicates}")
        if errors:
            log_lines.append(f"أخطاء: {errors}")

        self.write({
            'state': 'done',
            'sent_count': sent,
            'duplicate_count': duplicates,
            'log': (self.log or '') + '\n\n--- نتيجة الإرسال ---\n' +
                   '\n'.join(log_lines),
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('تم الإرسال'),
                'message': _('تم إرسال %s سجل، تم تخطي %s مكرر') % (
                    sent, duplicates),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_reset(self):
        self.ensure_one()
        self.write({
            'state': 'draft',
            'log': False,
            'total_rows': 0,
            'valid_rows': 0,
            'error_rows': 0,
            'sent_count': 0,
            'duplicate_count': 0,
        })
