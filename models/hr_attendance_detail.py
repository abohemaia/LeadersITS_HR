from odoo import api, fields, models


MONTH_SELECTION = [
    ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'),
    ('4', 'أبريل'), ('5', 'مايو'), ('6', 'يونيو'),
    ('7', 'يوليو'), ('8', 'أغسطس'), ('9', 'سبتمبر'),
    ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
]


class LeadersitsHrAttendanceDetail(models.Model):
    _name = 'leadersits.hr.attendance.detail'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'الحضور والانصراف تفصيلي'
    _order = 'att_year desc, att_month desc, employee_name asc, calc_date asc, tr_dt asc'

    _sql_constraints = [
        ('employee_trdt_unique',
         'UNIQUE(employee_id, tr_dt)',
         'لا يمكن تكرار نفس وقت الحركة لنفس الموظف!'),
    ]

    employee_id = fields.Many2one(
        'hr.employee', string="الموظف", required=True, ondelete='cascade',
        tracking=True)
    employee_name = fields.Char(
        related='employee_id.name',
        string="اسم الموظف", store=True, readonly=True)
    employee_code = fields.Char(
        related='employee_id.lits_employee_code',
        string="كود الموظف", store=True, readonly=True)
    calc_date = fields.Date(string="تاريخ الحساب", required=True, tracking=True)
    tr_dt = fields.Datetime(string="وقت الحركة", tracking=True)
    direction = fields.Selection([
        ('--', 'غير محدد'),
        ('in', 'حضور'),
        ('out', 'انصراف'),
    ], string="الاتجاه", default='--', tracking=True)
    latitude = fields.Float(string="خط العرض", digits=(10, 7), tracking=True)
    longitude = fields.Float(string="خط الطول", digits=(10, 7), tracking=True)
    tr_type = fields.Selection([
        ('manual', 'Manual'),
        ('excel', 'Excel'),
        ('tam', 'TAM'),
        ('mapp', 'MApp'),
        ('appdb', 'AppDB'),
        ('system', 'System'),
    ], string="نوع الحركة", default='manual', tracking=True)

    lits_adjusted = fields.Integer(string="ضبط", default=0)

    def write(self, vals):
        if 'tr_dt' in vals and 'tr_type' not in vals:
            vals['tr_type'] = 'manual'
        reset_fields = {'tr_dt', 'direction', 'calc_date'}
        if reset_fields & set(vals.keys()) and 'lits_adjusted' not in vals:
            vals['lits_adjusted'] = 0
        return super().write(vals)

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
