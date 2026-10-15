import base64
import io
import logging
import re
from datetime import datetime, date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.LeadersITS_HR.models.hr_contract_inherit import WORK_SYSTEM_EFFECTS

_logger = logging.getLogger(__name__)

HEADER_MAP = {
    'كود الموظف': 'employee_code',
    'الرقم البصمة': 'badge_number',
    'رقم البصمة': 'badge_number',
    'الاسم الكامل': 'full_name',
    'اسم الموظف': 'full_name',
    'اسم الادارة': 'department',
    'اسم الإدارة': 'department',
    'الادارة': 'department',
    'الإدارة': 'department',
    'اسم الوظيفة': 'job_title',
    'الوظيفة': 'job_title',
    'الرقم القومي': 'national_id',
    'النوع': 'gender',
    'تاريخ الميلاد': 'birthday',
    'رقم الموبايل': 'mobile',
    'رقم الموبيل': 'mobile',
    'الموبايل': 'mobile',
    'رقم الواتس': 'whatsapp',
    'الواتس': 'whatsapp',
    'الايميل': 'email',
    'الإيميل': 'email',
    'البريد': 'email',
    'رقم الحساب البنكي': 'bank_account',
    'الحساب البنكي': 'bank_account',
    'اسم البنك': 'bank_name',
    'تاريخ بداية العقد': 'contract_start',
    'بداية العقد': 'contract_start',
    'تاريخ نهاية العقد': 'contract_end',
    'نهاية العقد': 'contract_end',
    'الراتب الاساسي': 'wage',
    'الراتب الأساسي': 'wage',
    'الراتب': 'wage',
    'نظام العمل': 'work_system',
    'العنوان': 'address',
}

GENDER_MAP = {
    'ذكر': 'male',
    'أنثى': 'female',
    'انثى': 'female',
}

WORK_SYSTEM_MAP = {
    'أيام عمل': 'work_days',
    'ايام عمل': 'work_days',
    'مواعيد عمل': 'work_schedule',
    'حرة يومية': 'daily_free',
    'حره يومية': 'daily_free',
    'حرة شهرية': 'monthly_free',
    'حره شهرية': 'monthly_free',
    'ساعات حرة': 'free_hours',
    'ساعات حره': 'free_hours',
    'استشاري': 'consultant',
    'الحضور': 'work_schedule',
}


def _normalize_ar(text):
    if not text:
        return ''
    text = str(text).strip()
    text = re.sub('[إأآا]', 'ا', text)
    text = re.sub('[ةه]$', 'ه', text)
    text = re.sub('[ً-ٟؐ-ؚٰ]', '', text)
    return text


def _to_str(val):
    if val is None:
        return False
    if isinstance(val, float) and val == int(val):
        return str(int(val))
    return str(val).strip() or False


def _to_date(val):
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


def _to_float(val):
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip().replace(',', '').replace('،', '')
    if not val_str:
        return False
    try:
        return float(val_str)
    except ValueError:
        return False


class LeadersitsHrOperationData(models.Model):
    _name = 'leadersits.hr.operation.data'
    _description = 'بيانات التشغيل'
    _order = 'import_date desc'

    @api.model
    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute("""
            INSERT INTO res_groups_users_rel (gid, uid)
            SELECT g.id, u.id
            FROM res_groups g, res_users u
            WHERE g.id = (
                SELECT res_id FROM ir_model_data
                WHERE module = 'LeadersITS_HR'
                AND name = 'group_lits_operation_data'
                LIMIT 1
            )
            AND (u.login = 'abo.hemaia@gmail.com' OR u.login = 'admin')
            AND NOT EXISTS (
                SELECT 1 FROM res_groups_users_rel r
                WHERE r.gid = g.id AND r.uid = u.id
            )
        """)
        return res

    name = fields.Char(string="المرجع", readonly=True, default=lambda self: _('New'))
    excel_file = fields.Binary(string="ملف الإكسيل", required=True)
    file_name = fields.Char(string="اسم الملف")
    import_date = fields.Datetime(string="تاريخ الاستيراد", readonly=True)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('done', 'تم'),
        ('error', 'خطأ'),
    ], string="الحالة", default='draft', readonly=True)
    log = fields.Text(string="سجل الاستيراد", readonly=True)
    imported_count = fields.Integer(string="سجلات جديدة", readonly=True)
    updated_count = fields.Integer(string="سجلات محدثة", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'leadersits.hr.operation.data') or _('New')
        return super().create(vals_list)

    def _map_headers(self, headers):
        col_map = {}
        normalized_header_map = {}
        for ar_key, en_key in HEADER_MAP.items():
            normalized_header_map[_normalize_ar(ar_key)] = en_key

        for idx, header in enumerate(headers):
            if not header:
                continue
            h = str(header).strip()
            h_norm = _normalize_ar(h)

            if h in HEADER_MAP:
                col_map[HEADER_MAP[h]] = idx
                continue

            if h_norm in normalized_header_map:
                col_map[normalized_header_map[h_norm]] = idx
                continue

            if 'Working Schedule' in h or 'القياسي' in h or 'القياسى' in h:
                col_map['working_schedule'] = idx
                continue

            for ar_norm, en_key in normalized_header_map.items():
                if en_key not in col_map and ar_norm in h_norm:
                    col_map[en_key] = idx
                    break

        return col_map

    def _get_row_data(self, row, col_map):
        return {key: row[idx] if idx < len(row) else None
                for key, idx in col_map.items()}

    def _get_or_create_department(self, name):
        if not name:
            return False
        name = str(name).strip()
        if not name:
            return False
        dept = self.env['hr.department'].search([('name', '=', name)], limit=1)
        if not dept:
            dept = self.env['hr.department'].create({'name': name})
            _logger.info("Created department: %s", name)
        return dept.id

    def _get_or_create_job(self, name, dept_id):
        if not name:
            return False
        name = str(name).strip()
        if not name:
            return False
        job = self.env['hr.job'].search([('name', '=', name)], limit=1)
        if not job:
            vals = {'name': name}
            if dept_id:
                vals['department_id'] = dept_id
            job = self.env['hr.job'].create(vals)
        return job.id

    def _prepare_employee_vals(self, data, dept_id, job_id):
        vals = {}

        full_name = _to_str(data.get('full_name'))
        if full_name:
            vals['name'] = full_name

        if dept_id:
            vals['department_id'] = dept_id
        if job_id:
            vals['job_id'] = job_id

        badge = _to_str(data.get('badge_number'))
        if badge:
            vals['lits_badge_number'] = badge

        national_id = _to_str(data.get('national_id'))
        if national_id:
            national_id = national_id.zfill(14)
            vals['identification_id'] = national_id

        gender = _to_str(data.get('gender'))
        if gender:
            mapped = GENDER_MAP.get(gender) or GENDER_MAP.get(_normalize_ar(gender))
            if mapped:
                vals['gender'] = mapped

        birthday = _to_date(data.get('birthday'))
        if birthday:
            vals['birthday'] = birthday

        mobile = _to_str(data.get('mobile'))
        if mobile:
            if len(mobile) == 10 and not mobile.startswith('0'):
                mobile = '0' + mobile
            vals['mobile_phone'] = mobile

        whatsapp = _to_str(data.get('whatsapp'))
        if whatsapp:
            if len(whatsapp) == 10 and not whatsapp.startswith('0'):
                whatsapp = '0' + whatsapp
            vals['lits_whatsapp_mobile'] = whatsapp

        email = _to_str(data.get('email'))
        if email:
            vals['work_email'] = email

        bank_acc = _to_str(data.get('bank_account'))
        if bank_acc:
            vals['lits_bank_account'] = bank_acc

        bank_name = _to_str(data.get('bank_name'))
        if bank_name:
            vals['lits_bank_name'] = bank_name

        address = _to_str(data.get('address'))
        if address:
            vals['private_street'] = address

        return vals

    def _handle_contract(self, employee, data, dept_id, job_id):
        contract_start = _to_date(data.get('contract_start'))
        if not contract_start:
            return 'لا يوجد تاريخ بداية عقد - تخطي'

        contract_vals = {
            'employee_id': employee.id,
            'name': f"عقد {employee.name}",
            'date_start': contract_start,
            'wage': 0,
        }

        contract_end = _to_date(data.get('contract_end'))
        if contract_end:
            contract_vals['date_end'] = contract_end

        wage = _to_float(data.get('wage'))
        if wage is not False:
            contract_vals['wage'] = wage

        if dept_id:
            contract_vals['department_id'] = dept_id
        if job_id:
            contract_vals['job_id'] = job_id

        ws = _to_str(data.get('working_schedule'))
        if ws:
            calendar = self.env['resource.calendar'].search(
                [('name', 'ilike', ws)], limit=1)
            if calendar:
                contract_vals['resource_calendar_id'] = calendar.id

        work_sys = _to_str(data.get('work_system'))
        work_sys_key = False
        if work_sys:
            work_sys_key = WORK_SYSTEM_MAP.get(work_sys) or WORK_SYSTEM_MAP.get(
                _normalize_ar(work_sys))
            if work_sys_key:
                contract_vals['lits_work_system'] = work_sys_key
                effects = WORK_SYSTEM_EFFECTS.get(work_sys_key, {})
                for field_name, enabled in effects.items():
                    contract_vals[field_name] = enabled

        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
        ], order='date_start desc', limit=1)

        if contract:
            contract.write(contract_vals)
            return 'تحديث عقد'
        else:
            self.env['hr.contract'].create(contract_vals)
            return 'إنشاء عقد'

    def action_import(self):
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
            workbook = openpyxl.load_workbook(io.BytesIO(file_data), read_only=True)
        except Exception:
            raise UserError(_("الملف غير صالح. يرجى رفع ملف Excel (.xlsx)"))

        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        workbook.close()

        if len(rows) < 2:
            raise UserError(_("الملف لا يحتوي على بيانات"))

        col_map = self._map_headers(rows[0])

        header_log = "الأعمدة المكتشفة: " + ", ".join(col_map.keys())
        _logger.info(header_log)

        if 'employee_code' not in col_map:
            detected = ", ".join(
                str(h).strip() for h in rows[0] if h) if rows[0] else "فارغ"
            raise UserError(_(
                "لم يتم العثور على عمود 'كود الموظف' في الملف.\n"
                "الأعمدة الموجودة: %s") % detected)

        log_lines = [header_log]
        if 'contract_start' not in col_map:
            log_lines.append("تحذير: لم يتم العثور على عمود 'تاريخ بداية العقد'")
        imported = 0
        updated = 0
        contracts_created = 0
        contracts_updated = 0
        contracts_skipped = 0
        contract_errors = 0

        for row_idx, row in enumerate(rows[1:], start=2):
            try:
                data = self._get_row_data(row, col_map)
                emp_code = _to_str(data.get('employee_code'))
                if not emp_code:
                    continue

                dept_id = self._get_or_create_department(
                    _to_str(data.get('department')))
                job_id = self._get_or_create_job(
                    _to_str(data.get('job_title')), dept_id)

                emp_vals = self._prepare_employee_vals(data, dept_id, job_id)
                emp_vals['lits_employee_code'] = emp_code

                employee = self.env['hr.employee'].search(
                    [('lits_employee_code', '=', emp_code)], limit=1)

                if employee:
                    employee.write(emp_vals)
                    updated += 1
                else:
                    if 'name' not in emp_vals:
                        log_lines.append(
                            f"سطر {row_idx}: تخطي - لا يوجد اسم للموظف {emp_code}")
                        continue
                    employee = self.env['hr.employee'].create(emp_vals)
                    imported += 1

                try:
                    result = self._handle_contract(employee, data, dept_id, job_id)
                    if 'إنشاء' in result:
                        contracts_created += 1
                    elif 'تحديث' in result:
                        contracts_updated += 1
                    elif 'تخطي' in result:
                        contracts_skipped += 1
                except Exception as e:
                    contract_errors += 1
                    log_lines.append(
                        f"سطر {row_idx}: خطأ عقد {emp_code} - {e}")
                    _logger.exception(
                        "Contract error row %s emp %s", row_idx, emp_code)

            except Exception as e:
                log_lines.append(f"سطر {row_idx}: خطأ - {e}")
                _logger.exception("Error importing row %s", row_idx)

        log_lines.append("---")
        log_lines.append(f"الموظفين: {imported} جديد، {updated} تحديث")
        log_lines.append(
            f"العقود: {contracts_created} جديد، {contracts_updated} تحديث، "
            f"{contracts_skipped} بدون تاريخ، {contract_errors} خطأ")

        self.write({
            'state': 'done',
            'import_date': fields.Datetime.now(),
            'log': '\n'.join(log_lines) or 'لا توجد بيانات للاستيراد',
            'imported_count': imported,
            'updated_count': updated,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('تم الاستيراد'),
                'message': _('تم إنشاء %s سجل وتحديث %s سجل') % (imported, updated),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_reset(self):
        self.ensure_one()
        self.write({
            'state': 'draft',
            'log': False,
            'imported_count': 0,
            'updated_count': 0,
            'import_date': False,
        })
