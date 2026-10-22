import calendar
from datetime import date, datetime, timedelta

import pytz

from odoo import api, fields, models


YEAR_SELECTION = [(str(y), str(y)) for y in range(2025, 2041)]

MONTH_SELECTION = [
    ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'),
    ('4', 'أبريل'), ('5', 'مايو'), ('6', 'يونيو'),
    ('7', 'يوليو'), ('8', 'أغسطس'), ('9', 'سبتمبر'),
    ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
]

MONTH_NAMES = dict(MONTH_SELECTION)


def _calc_dates(env, calc_year, calc_month):
    if not calc_year or not calc_month:
        return False, False
    year = int(calc_year)
    month = int(calc_month)
    config = env['leadersits.hr.time.config'].search([], limit=1)
    is_custom = config and config.month_calc == 'custom'
    start_day = config.month_start_day if is_custom and config.month_start_day else 1
    end_day = config.month_end_day if is_custom and config.month_end_day else 0

    if is_custom and start_day > 1:
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        max_day_prev = calendar.monthrange(prev_year, prev_month)[1]
        actual_start = min(start_day, max_day_prev)
        d_from = date(prev_year, prev_month, actual_start)
        if end_day:
            max_day_cur = calendar.monthrange(year, month)[1]
            actual_end = min(end_day, max_day_cur)
            d_to = date(year, month, actual_end)
        else:
            actual_end = min(start_day - 1, calendar.monthrange(year, month)[1])
            d_to = date(year, month, actual_end)
    else:
        d_from = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        d_to = date(year, month, last_day)
    return d_from, d_to


class LeadersitsHrCalcProcess(models.Model):
    _name = 'leadersits.hr.calc.process'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'اجراء حساب'
    _order = 'create_date desc'

    name = fields.Char(string="المرجع", default="جديد", tracking=True)
    notes = fields.Text(string="ملاحظات")

    calc_year = fields.Selection(
        YEAR_SELECTION, string="السنة", required=True,
        default=lambda self: str(fields.Date.context_today(self).year),
        tracking=True)
    calc_month = fields.Selection(
        MONTH_SELECTION, string="الشهر", required=True,
        default=lambda self: str(fields.Date.context_today(self).month),
        tracking=True)
    date_from = fields.Date(string="من", compute='_compute_dates', store=True)
    date_to = fields.Date(string="الى", compute='_compute_dates', store=True)

    target_type = fields.Selection([
        ('company', 'الشركة'),
        ('employee', 'الموظف'),
        ('department', 'القسم'),
        ('job', 'الوظيفة'),
    ], string="الوضع", required=True, default='company', tracking=True)

    company_ids = fields.Many2many(
        'res.company', 'calc_process_company_rel',
        'calc_id', 'company_id', string="الشركة",
        default=lambda self: self.env.company)
    employee_ids = fields.Many2many(
        'hr.employee', 'calc_process_employee_rel',
        'calc_id', 'employee_id', string="الموظف")
    department_ids = fields.Many2many(
        'hr.department', 'calc_process_department_rel',
        'calc_id', 'department_id', string="القسم")
    job_ids = fields.Many2many(
        'hr.job', 'calc_process_job_rel',
        'calc_id', 'job_id', string="الوظيفة")

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('done', 'تم الحساب'),
    ], string="الحالة", default='draft', readonly=True, tracking=True)

    @api.depends('calc_year', 'calc_month')
    def _compute_dates(self):
        for rec in self:
            d_from, d_to = _calc_dates(self.env, rec.calc_year, rec.calc_month)
            rec.date_from = d_from
            rec.date_to = d_to

    @api.onchange('target_type')
    def _onchange_target_type(self):
        self.company_ids = [(5,)]
        self.employee_ids = [(5,)]
        self.department_ids = [(5,)]
        self.job_ids = [(5,)]

    def _get_target_summary(self):
        self.ensure_one()
        tt = dict(self._fields['target_type'].selection).get(self.target_type, '')
        if self.target_type == 'company':
            names = ', '.join(self.company_ids.mapped('name')) or '-'
        elif self.target_type == 'employee':
            names = ', '.join(self.employee_ids.mapped('name')) or '-'
        elif self.target_type == 'department':
            names = ', '.join(self.department_ids.mapped('name')) or '-'
        elif self.target_type == 'job':
            names = ', '.join(self.job_ids.mapped('name')) or '-'
        else:
            names = '-'
        return tt, names

    def _get_target_employees(self):
        self.ensure_one()
        Employee = self.env['hr.employee']
        if self.target_type == 'company':
            return Employee.search([
                ('company_id', 'in', self.company_ids.ids)])
        elif self.target_type == 'employee':
            return self.employee_ids
        elif self.target_type == 'department':
            return Employee.search([
                ('department_id', 'in', self.department_ids.ids)])
        elif self.target_type == 'job':
            return Employee.search([
                ('job_id', 'in', self.job_ids.ids)])
        return Employee

    def action_calculate(self):
        self.ensure_one()
        month_name = MONTH_NAMES.get(self.calc_month, '')
        tt_label, tt_names = self._get_target_summary()
        message = (
            f"هل تريد اجراء الحساب؟\n\n"
            f"السنة: {self.calc_year}\n"
            f"الشهر: {month_name}\n"
            f"من: {self.date_from}\n"
            f"الى: {self.date_to}\n"
            f"{tt_label}: {tt_names}"
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'leadersits.hr.calc.process.confirm',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_calc_process_id': self.id,
                'default_message': message,
            },
        }


class LeadersitsHrCalcProcessConfirm(models.TransientModel):
    _name = 'leadersits.hr.calc.process.confirm'
    _description = 'تأكيد اجراء حساب'

    calc_process_id = fields.Many2one(
        'leadersits.hr.calc.process', required=True)
    message = fields.Text(string="تفاصيل", readonly=True)

    def action_confirm(self):
        self.ensure_one()
        process = self.calc_process_id

        employees = process._get_target_employees()
        if not employees:
            raise models.ValidationError('لا يوجد موظفين مطابقين للاختيار.')

        d_from = process.date_from
        d_to = process.date_to
        if not d_from or not d_to:
            raise models.ValidationError('لم يتم تحديد تواريخ الشهر.')

        Detail = self.env['leadersits.hr.attendance.detail']
        Attendance = self.env['leadersits.hr.attendance.its']
        Leave = self.env['hr.leave']
        ScheduleEx = self.env['leadersits.hr.schedule.exception']
        CalcEx = self.env['leadersits.hr.calc.exception']

        config = self.env['leadersits.hr.time.config'].search([], limit=1)
        calc_method = config.calc_method if config else 'daily'
        missing_punch = config.missing_punch if config else 'leave_empty'
        ctx = {'skip_detail_sync': True, 'tracking_disable': True}

        all_days = []
        current = d_from
        while current <= d_to:
            all_days.append(current)
            current += timedelta(days=1)

        for employee in employees.sorted(key=lambda e: e.name or ''):
            existing_att = Attendance.with_context(**ctx).search([
                ('employee_id', '=', employee.id),
                ('calc_date', '>=', d_from),
                ('calc_date', '<=', d_to),
            ])
            if existing_att:
                existing_att.with_context(**ctx).unlink()

            detail_records = Detail.search([
                ('employee_id', '=', employee.id),
                ('att_year', '=', process.calc_year),
                ('att_month', '=', process.calc_month),
            ])

            emp_leaves = Leave.search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('request_date_from', '<=', d_to),
                ('request_date_to', '>=', d_from),
            ])

            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open'),
            ], limit=1)
            if not contract:
                contract = self.env['hr.contract'].search([
                    ('employee_id', '=', employee.id),
                ], order='date_start desc', limit=1)

            schedule_exceptions = ScheduleEx.search([
                ('date_from', '<=', d_to),
                ('date_to', '>=', d_from),
                '|', '|',
                '&', ('target_type', '=', 'employee'),
                     ('employee_ids', 'in', [employee.id]),
                '&', ('target_type', '=', 'department'),
                     ('department_ids', 'in', [employee.department_id.id] if employee.department_id else []),
                '&', ('target_type', '=', 'job'),
                     ('job_ids', 'in', [employee.job_id.id] if employee.job_id else []),
            ])

            calc_exceptions = CalcEx.search([
                ('date_from', '<=', d_to),
                ('date_to', '>=', d_from),
                '|', '|',
                '&', ('target_type', '=', 'employee'),
                     ('employee_ids', 'in', [employee.id]),
                '&', ('target_type', '=', 'department'),
                     ('department_ids', 'in', [employee.department_id.id] if employee.department_id else []),
                '&', ('target_type', '=', 'job'),
                     ('job_ids', 'in', [employee.job_id.id] if employee.job_id else []),
            ])

            dates_detail = {}
            for rec in detail_records:
                d = rec.calc_date
                if d not in dates_detail:
                    dates_detail[d] = Detail
                dates_detail[d] |= rec

            contract_ch_vals = {
                'lits_ch_late': contract.eff_late if contract else False,
                'lits_ch_day_out': contract.eff_leave_during if contract else False,
                'lits_ch_early_leave': contract.eff_early_leave if contract else False,
                'lits_ch_punch_error': contract.eff_punch_error if contract else False,
                'lits_ch_absence': contract.eff_absence if contract else False,
                'lits_ch_location': contract.eff_location_error if contract else False,
                'lits_ch_ot_morning': contract.eff_morning_ot if contract else False,
                'lits_ch_ot_evening': contract.eff_evening_ot if contract else False,
            }

            for day in all_days:
                ch_vals = self._get_ch_vals_for_day(
                    contract_ch_vals, calc_exceptions, day)
                day_calendar = self._get_day_calendar(
                    employee, contract, schedule_exceptions, day)
                shift_name = day_calendar.name if day_calendar else ''
                shift_hours = self._get_shift_hours(day_calendar, day)

                leave_for_day = self._get_leave_for_day(emp_leaves, day)

                day_details = dates_detail.get(day)

                calc_val = 1 if shift_hours else 0

                if day_details:
                    self._process_day_attendance(
                        employee, day, day_details, shift_name,
                        shift_hours, leave_for_day, calc_method, ctx,
                        ch_vals, calc_val, missing_punch)
                elif leave_for_day:
                    self._process_day_leave(
                        employee, day, leave_for_day, shift_name,
                        shift_hours, ctx, ch_vals, calc_val)
                else:
                    is_work_day = bool(shift_hours)
                    day_type = 'غياب بدون اذن' if is_work_day else 'اجازة اسبوعية'
                    vals = {
                        'employee_id': employee.id,
                        'calc_date': day,
                        'check_in': False,
                        'check_out': False,
                        'day_type': day_type,
                        'shift': shift_name,
                        'calc': calc_val,
                    }
                    vals.update(ch_vals)
                    Attendance.with_context(**ctx).create(vals)

            emp_att = Attendance.with_context(**ctx).search([
                ('employee_id', '=', employee.id),
                ('calc_date', '>=', d_from),
                ('calc_date', '<=', d_to),
            ], order='calc_date asc, check_in asc')
            current_date = None
            seq = 0
            for att in emp_att:
                if att.calc_date != current_date:
                    current_date = att.calc_date
                    seq = 1
                else:
                    seq += 1
                att.with_context(**ctx).write({'d_id': seq})

        process.write({'state': 'done'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'leadersits.hr.calc.process',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def _local_hour_to_utc(self, day, hour_float, employee):
        local_tz = pytz.timezone(employee.tz or self.env.company.tz or 'UTC')
        naive_local = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour_float)
        local_dt = local_tz.localize(naive_local)
        return local_dt.astimezone(pytz.utc).replace(tzinfo=None)

    def _get_day_calendar(self, employee, contract, schedule_exceptions, day):
        for exc in schedule_exceptions:
            if exc.date_from <= day <= exc.date_to:
                return exc.resource_calendar_id

        if contract and contract.resource_calendar_id:
            return contract.resource_calendar_id

        if employee.resource_calendar_id:
            return employee.resource_calendar_id

        return False

    def _get_shift_hours(self, calendar_rec, day):
        if not calendar_rec:
            return []
        dow = str(day.weekday())
        attendances = calendar_rec.attendance_ids.filtered(
            lambda a: a.dayofweek == dow and a.day_period != 'lunch')
        if not attendances:
            return []
        result = []
        for att in attendances.sorted(key=lambda a: a.hour_from):
            result.append({
                'hour_from': att.hour_from,
                'hour_to': att.hour_to,
                'day_period': att.day_period,
            })
        return result

    def _get_leave_for_day(self, leaves, day):
        for leave in leaves:
            if leave.request_date_from <= day <= leave.request_date_to:
                return leave
        return False

    def _process_day_attendance(self, employee, day, detail_recs,
                                shift_name, shift_hours, leave_for_day,
                                calc_method, ctx, ch_vals, calc_val,
                                missing_punch):
        Attendance = self.env['leadersits.hr.attendance.its']

        sorted_recs = detail_recs.sorted(
            key=lambda r: r.tr_dt or fields.Datetime.min)

        first_is_checkin = True
        if len(sorted_recs) % 2 != 0 and shift_hours and sorted_recs[0].tr_dt:
            shift_start = shift_hours[0]['hour_from']
            shift_end = shift_hours[-1]['hour_to']
            midpoint = (shift_start + shift_end) / 2.0
            first_dt = sorted_recs[0].tr_dt
            try:
                import pytz
                tz = pytz.timezone(employee.tz or 'UTC')
                local_dt = first_dt.replace(tzinfo=pytz.utc).astimezone(tz)
                first_hour = local_dt.hour + local_dt.minute / 60.0
            except Exception:
                first_hour = first_dt.hour + first_dt.minute / 60.0
            if first_hour >= midpoint:
                first_is_checkin = False

        for i, rec in enumerate(sorted_recs):
            if first_is_checkin:
                direction = 'in' if i % 2 == 0 else 'out'
            else:
                direction = 'out' if i % 2 == 0 else 'in'
            rec.with_context(tracking_disable=True).write({
                'direction': direction, 'lits_adjusted': 1})

        leave_type_name = leave_for_day.holiday_status_id.name if leave_for_day else False
        if leave_for_day:
            payed_val = 2 if leave_for_day.holiday_status_id.unpaid else 1
        else:
            payed_val = 0
        fill_from_shift = missing_punch == 'from_shift' and bool(shift_hours)

        if first_is_checkin:
            for i in range(0, len(sorted_recs), 2):
                checkin_rec = sorted_recs[i]
                checkout_rec = sorted_recs[i + 1] if i + 1 < len(sorted_recs) else None
                check_in_time = checkin_rec.tr_dt
                check_out_time = checkout_rec.tr_dt if checkout_rec else False
                if checkout_rec:
                    row_type = leave_type_name or 'حضور - انصراف'
                elif fill_from_shift:
                    shift_end = shift_hours[-1]['hour_to']
                    check_out_time = self._local_hour_to_utc(
                        day, shift_end, employee)
                    row_type = leave_type_name or 'حضور فقط'
                else:
                    row_type = leave_type_name or 'حضور فقط'
                vals = {
                    'employee_id': employee.id,
                    'calc_date': day,
                    'check_in': check_in_time,
                    'check_out': check_out_time,
                    'day_type': row_type,
                    'shift': shift_name,
                    'latitude_in': checkin_rec.latitude,
                    'longitude_in': checkin_rec.longitude,
                    'latitude_out': checkout_rec.latitude if checkout_rec else 0,
                    'longitude_out': checkout_rec.longitude if checkout_rec else 0,
                    'lits_detail_checkin_id': checkin_rec.id,
                    'lits_detail_checkout_id': checkout_rec.id if checkout_rec else False,
                    'calc': calc_val,
                    'payed': payed_val,
                }
                vals.update(ch_vals)
                Attendance.with_context(**ctx).create(vals)
        else:
            first_rec = sorted_recs[0]
            check_in_time = False
            if fill_from_shift:
                shift_start = shift_hours[0]['hour_from']
                check_in_time = self._local_hour_to_utc(
                    day, shift_start, employee)
            row_type = leave_type_name or 'انصراف فقط'
            vals = {
                'employee_id': employee.id,
                'calc_date': day,
                'check_in': check_in_time,
                'check_out': first_rec.tr_dt,
                'day_type': row_type,
                'shift': shift_name,
                'latitude_in': 0,
                'longitude_in': 0,
                'latitude_out': first_rec.latitude,
                'longitude_out': first_rec.longitude,
                'lits_detail_checkin_id': False,
                'lits_detail_checkout_id': first_rec.id,
                'calc': calc_val,
                'payed': payed_val,
            }
            vals.update(ch_vals)
            Attendance.with_context(**ctx).create(vals)

            for i in range(1, len(sorted_recs), 2):
                checkin_rec = sorted_recs[i]
                checkout_rec = sorted_recs[i + 1] if i + 1 < len(sorted_recs) else None
                check_in_time = checkin_rec.tr_dt
                check_out_time = checkout_rec.tr_dt if checkout_rec else False
                if checkout_rec:
                    pair_type = leave_type_name or 'حضور - انصراف'
                elif fill_from_shift:
                    shift_end = shift_hours[-1]['hour_to']
                    check_out_time = self._local_hour_to_utc(
                        day, shift_end, employee)
                    pair_type = leave_type_name or 'حضور فقط'
                else:
                    pair_type = leave_type_name or 'حضور فقط'
                vals = {
                    'employee_id': employee.id,
                    'calc_date': day,
                    'check_in': check_in_time,
                    'check_out': check_out_time,
                    'day_type': pair_type,
                    'shift': shift_name,
                    'latitude_in': checkin_rec.latitude,
                    'longitude_in': checkin_rec.longitude,
                    'latitude_out': checkout_rec.latitude if checkout_rec else 0,
                    'longitude_out': checkout_rec.longitude if checkout_rec else 0,
                    'lits_detail_checkin_id': checkin_rec.id,
                    'lits_detail_checkout_id': checkout_rec.id if checkout_rec else False,
                    'calc': calc_val,
                    'payed': payed_val,
                }
                vals.update(ch_vals)
                Attendance.with_context(**ctx).create(vals)

    def _process_day_leave(self, employee, day, leave, shift_name,
                           shift_hours, ctx, ch_vals, calc_val):
        Attendance = self.env['leadersits.hr.attendance.its']

        day_type = leave.holiday_status_id.name or 'اجازة'
        payed_val = 2 if leave.holiday_status_id.unpaid else 1

        if leave.request_unit_hours:
            check_in = leave.date_from
            check_out = leave.date_to
        else:
            if shift_hours:
                first_hour = shift_hours[0]['hour_from']
                last_hour = shift_hours[-1]['hour_to']
            else:
                first_hour = 8.0
                last_hour = 16.0
            check_in = leave.date_from if leave.request_date_from == day else \
                self._local_hour_to_utc(day, first_hour, employee)
            check_out = leave.date_to if leave.request_date_to == day else \
                self._local_hour_to_utc(day, last_hour, employee)

        vals = {
            'employee_id': employee.id,
            'calc_date': day,
            'check_in': check_in,
            'check_out': check_out,
            'day_type': day_type,
            'shift': shift_name,
            'calc': calc_val,
            'payed': payed_val,
        }
        vals.update(ch_vals)
        Attendance.with_context(**ctx).create(vals)

    def _get_ch_vals_for_day(self, contract_ch_vals, calc_exceptions, day):
        for exc in calc_exceptions:
            if exc.date_from <= day <= exc.date_to:
                return {
                    'lits_ch_late': exc.eff_late,
                    'lits_ch_day_out': exc.eff_leave_during,
                    'lits_ch_early_leave': exc.eff_early_leave,
                    'lits_ch_punch_error': exc.eff_punch_error,
                    'lits_ch_absence': exc.eff_absence,
                    'lits_ch_location': exc.eff_location_error,
                    'lits_ch_ot_morning': exc.eff_morning_ot,
                    'lits_ch_ot_evening': exc.eff_evening_ot,
                }
        return contract_ch_vals

    def _float_to_time_str(self, float_time):
        hours = int(float_time)
        minutes = int((float_time - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"
