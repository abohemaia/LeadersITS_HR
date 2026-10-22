from odoo import api, fields, models
from odoo.exceptions import UserError


class LeadersitsHrAttendanceIts(models.Model):
    _name = 'leadersits.hr.attendance.its'
    _description = 'الحضور والانصراف مجمعة'
    _order = 'att_year desc, att_month desc, employee_name asc, calc_date asc, check_in asc'

    employee_id = fields.Many2one(
        'hr.employee', string="الموظف", required=True,
        ondelete='cascade', index=True)
    employee_name = fields.Char(
        related='employee_id.name',
        string="اسم الموظف", store=True, readonly=True)
    calc_date = fields.Date(string="تاريخ اليوم", index=True)
    att_month = fields.Selection([
        ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'),
        ('4', 'أبريل'), ('5', 'مايو'), ('6', 'يونيو'),
        ('7', 'يوليو'), ('8', 'أغسطس'), ('9', 'سبتمبر'),
        ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
    ], string="الشهر", store=True, readonly=True,
        compute='_compute_att_period')
    att_year = fields.Char(
        string="السنة", size=4, store=True, readonly=True,
        compute='_compute_att_period')
    check_in = fields.Datetime(string="وقت الحضور")
    check_out = fields.Datetime(string="وقت الانصراف")
    day_type = fields.Char(string="نوع البيان")
    worked_hours = fields.Float(
        string="ساعات العمل", compute='_compute_worked_hours',
        store=True, readonly=True, group_operator='sum')
    shift = fields.Char(string="الشيفت")

    lits_late = fields.Float(string="التأخير", group_operator='sum')
    lits_day_out = fields.Float(string="خروج اليوم", group_operator='sum')
    lits_early_leave = fields.Float(string="انصراف مبكر", group_operator='sum')
    lits_punch_error = fields.Float(string="خطأ بصمه", group_operator='sum')
    lits_absence = fields.Float(string="الغياب", group_operator='sum')
    lits_location = fields.Float(string="الموقع", group_operator='sum')
    lits_ot_morning = fields.Float(string="الاضافي الصباحي", group_operator='sum')
    lits_ot_evening = fields.Float(string="الاضافي المسائي", group_operator='sum')
    lits_total = fields.Float(string="الاجمالي", group_operator='sum')

    lits_ch_late = fields.Boolean(string="Ch التأخير")
    lits_ch_day_out = fields.Boolean(string="Ch خروج")
    lits_ch_early_leave = fields.Boolean(string="Ch انصراف")
    lits_ch_punch_error = fields.Boolean(string="Ch بصمه")
    lits_ch_absence = fields.Boolean(string="Ch الغياب")
    lits_ch_location = fields.Boolean(string="Ch اللوكيشن")
    lits_ch_ot_morning = fields.Boolean(string="Ch OTM")
    lits_ch_ot_evening = fields.Boolean(string="Ch OTL")

    latitude_in = fields.Float(string="Latitude In", digits=(10, 7))
    longitude_in = fields.Float(string="Longitude In", digits=(10, 7))
    latitude_out = fields.Float(string="Latitude Out", digits=(10, 7))
    longitude_out = fields.Float(string="Longitude Out", digits=(10, 7))

    calc = fields.Integer(string="Calc", default=0)
    payed = fields.Integer(string="Payed", default=0)
    d_id = fields.Integer(string="DId", default=0)

    lits_detail_checkin_id = fields.Many2one(
        'leadersits.hr.attendance.detail', string="صف الحضور التفصيلي",
        ondelete='set null', copy=False)
    lits_detail_checkout_id = fields.Many2one(
        'leadersits.hr.attendance.detail', string="صف الانصراف التفصيلي",
        ondelete='set null', copy=False)

    @api.depends('calc_date')
    def _compute_att_period(self):
        config = self.env['leadersits.hr.time.config'].search([], limit=1)
        is_custom = config and config.month_calc == 'custom'
        start_day = config.month_start_day if is_custom else 1

        for rec in self:
            if not rec.calc_date:
                rec.att_month = False
                rec.att_year = False
                continue

            dt = rec.calc_date
            if is_custom and start_day > 1:
                if dt.day < start_day:
                    period_month = dt.month
                    period_year = dt.year
                else:
                    period_month = dt.month + 1
                    if period_month > 12:
                        period_month = 1
                        period_year = dt.year + 1
                    else:
                        period_year = dt.year
            else:
                period_month = dt.month
                period_year = dt.year

            rec.att_month = str(period_month)
            rec.att_year = str(period_year)

    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        for rec in self:
            if rec.check_in and rec.check_out:
                delta = rec.check_out - rec.check_in
                rec.worked_hours = delta.total_seconds() / 3600.0
            else:
                rec.worked_hours = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('skip_detail_sync'):
            raise UserError(
                'لا يمكن إضافة سجلات من هذه الشاشة.\n'
                'يرجى استخدام شاشة الحضور التفصيلي ثم إجراء الحساب.')
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('skip_detail_sync'):
            raise UserError(
                'لا يمكن تعديل سجلات من هذه الشاشة.\n'
                'يرجى استخدام شاشة الحضور التفصيلي ثم إجراء الحساب.')
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('skip_detail_sync'):
            raise UserError(
                'لا يمكن حذف سجلات من هذه الشاشة.\n'
                'يرجى استخدام شاشة الحضور التفصيلي ثم إجراء الحساب.')
        return super().unlink()
