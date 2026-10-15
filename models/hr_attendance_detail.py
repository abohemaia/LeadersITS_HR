from odoo import api, fields, models


MONTH_SELECTION = [
    ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'),
    ('4', 'أبريل'), ('5', 'مايو'), ('6', 'يونيو'),
    ('7', 'يوليو'), ('8', 'أغسطس'), ('9', 'سبتمبر'),
    ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
]


class LeadersitsHrAttendanceDetail(models.Model):
    _name = 'leadersits.hr.attendance.detail'
    _description = 'الحضور والانصراف تفصيلي'
    _order = 'calc_date desc, tr_dt desc'

    _sql_constraints = [
        ('employee_trdt_unique',
         'UNIQUE(employee_id, tr_dt)',
         'لا يمكن تكرار نفس وقت الحركة لنفس الموظف!'),
    ]

    employee_id = fields.Many2one(
        'hr.employee', string="الموظف", required=True, ondelete='cascade')
    employee_code = fields.Char(
        related='employee_id.lits_employee_code',
        string="كود الموظف", store=True, readonly=True)
    calc_date = fields.Date(string="تاريخ الحساب", required=True)
    tr_dt = fields.Datetime(string="وقت الحركة")
    direction = fields.Selection([
        ('--', 'غير محدد'),
        ('in', 'حضور'),
        ('out', 'انصراف'),
    ], string="الاتجاه", default='--')
    latitude_in = fields.Float(string="خط عرض الحضور", digits=(10, 7))
    longitude_in = fields.Float(string="خط طول الحضور", digits=(10, 7))
    latitude_out = fields.Float(string="خط عرض الانصراف", digits=(10, 7))
    longitude_out = fields.Float(string="خط طول الانصراف", digits=(10, 7))
    tr_type = fields.Selection([
        ('manual', 'Manual'),
        ('excel', 'Excel'),
        ('tam', 'TAM'),
        ('mapp', 'MApp'),
        ('appdb', 'AppDB'),
    ], string="نوع الحركة", default='manual')

    att_month = fields.Selection(
        MONTH_SELECTION, string="الشهر", store=True, readonly=True,
        compute='_compute_att_period')
    att_year = fields.Char(
        string="العام", size=4, store=True, readonly=True,
        compute='_compute_att_period')

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
