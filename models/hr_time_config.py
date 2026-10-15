from odoo import api, fields, models


class LeadersitsHrTimeConfig(models.Model):
    _name = 'leadersits.hr.time.config'
    _description = 'إعدادات حساب الحضور والانصراف'

    name = fields.Char(string="الاسم", required=True, default="إعدادات حساب الوقت")

    @api.model
    def action_open_config(self):
        config = self.search([], limit=1)
        if not config:
            config = self.create({'name': 'إعدادات حساب الوقت'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # --- الجزء العلوي ---
    month_calc = fields.Selection([
        ('normal', 'طبيعي'),
        ('custom', 'مخصص'),
    ], string="حساب الشهر", default='normal', required=True)
    month_start_day = fields.Integer(string="يوم بداية الشهر")
    month_end_day = fields.Integer(string="يوم نهاية الشهر")

    missing_punch = fields.Selection([
        ('from_shift', 'من الشيفت'),
        ('leave_empty', 'يترك فارغ'),
    ], string="بصمة ناقصة", default='from_shift', required=True)

    empty_punch_penalty = fields.Selection([
        ('minutes', 'دقائق'),
        ('quarter_day', 'ربع يوم'),
        ('half_day', 'نصف يوم'),
        ('full_day', 'يوم'),
    ], string="جزاء البصمة الفارغة", default='minutes', required=True)
    penalty_minutes = fields.Integer(string="عدد الدقائق")

    half_day_exit = fields.Selection([
        ('combined', 'مجمع'),
        ('independent', 'خروج مستقل'),
    ], string="الخروج نصف اليوم", default='combined', required=True)
    absence_multiplier = fields.Float(string="الغياب بدون إذن *", default=1)

    max_morning_ot = fields.Float(string="أقصى ساعات إضافي صباحي", default=999)
    max_evening_ot = fields.Float(string="أقصى ساعات إضافي مسائي", default=999)

    # --- الجزء السفلي (Tabs) ---
    late_line_ids = fields.One2many(
        'leadersits.hr.time.config.late', 'config_id', string="خطوط التأخير")
    overtime_line_ids = fields.One2many(
        'leadersits.hr.time.config.overtime', 'config_id', string="خطوط الإضافي")
    lits_line_ids = fields.One2many(
        'leadersits.hr.time.config.lits', 'config_id', string="خطوط LITS")

    @api.onchange('month_calc')
    def _onchange_month_calc(self):
        if self.month_calc == 'normal':
            self.month_start_day = 0
            self.month_end_day = 0

    @api.onchange('month_start_day')
    def _onchange_month_start_day(self):
        if self.month_start_day and self.month_calc == 'custom':
            start = int(self.month_start_day)
            if start < 1:
                start = 1
            if start > 31:
                start = 31
            self.month_start_day = start
            self.month_end_day = 31 if start == 1 else start - 1

    @api.onchange('empty_punch_penalty')
    def _onchange_empty_punch_penalty(self):
        if self.empty_punch_penalty != 'minutes':
            self.penalty_minutes = 0


class LeadersitsHrTimeConfigLate(models.Model):
    _name = 'leadersits.hr.time.config.late'
    _description = 'خطوط التأخير'

    config_id = fields.Many2one(
        'leadersits.hr.time.config', string="الإعدادات",
        required=True, ondelete='cascade')
    late_type = fields.Selection([
        ('late', 'تأخير'),
        ('exit', 'خروج'),
        ('early_leave', 'انصراف مبكر'),
    ], string="النوع", required=True, default='late')
    from_minutes = fields.Integer(string="من")
    to_minutes = fields.Integer(string="إلى")
    action_type = fields.Selection([
        ('x0', '*0'),
        ('x1', '*1'),
        ('x1_25', '*1.25'),
        ('x1_5', '*1.5'),
        ('x1_75', '*1.75'),
        ('x2', '*2'),
        ('quarter_day', '1/4 يوم'),
        ('half_day', '1/2 يوم'),
        ('full_day', 'يوم'),
        ('custom', 'مخصص'),
    ], string="الإجراء", required=True, default='x1')
    custom_value = fields.Float(string="مخصص", digits=(10, 2))

    @api.constrains('late_type', 'from_minutes', 'to_minutes')
    def _check_no_overlap(self):
        for rec in self:
            if rec.from_minutes >= rec.to_minutes:
                raise models.ValidationError(
                    'قيمة "من" يجب أن تكون أقل من قيمة "إلى"!')
            overlapping = self.search([
                ('config_id', '=', rec.config_id.id),
                ('late_type', '=', rec.late_type),
                ('id', '!=', rec.id),
                ('from_minutes', '<', rec.to_minutes),
                ('to_minutes', '>', rec.from_minutes),
            ])
            if overlapping:
                raise models.ValidationError(
                    'يوجد تداخل في الفترة مع سطر آخر من نفس النوع!')


class LeadersitsHrTimeConfigOvertime(models.Model):
    _name = 'leadersits.hr.time.config.overtime'
    _description = 'خطوط الإضافي'

    config_id = fields.Many2one(
        'leadersits.hr.time.config', string="الإعدادات",
        required=True, ondelete='cascade')
    ot_type = fields.Selection([
        ('morning', 'إضافي صباحي'),
        ('evening', 'إضافي مسائي'),
    ], string="النوع", required=True, default='morning')
    ot_category = fields.Selection([
        ('workday', 'يوم عمل'),
        ('weekly_off', 'إجازة أسبوعية'),
        ('official_holiday', 'إجازة رسمية'),
        ('vacation', 'عطلة'),
    ], string="الفئة", required=True, default='workday')
    ot_start = fields.Float(string="بداية الإضافي")
    action_type = fields.Selection([
        ('x0', '*0'),
        ('x1', '*1'),
        ('x1_25', '*1.25'),
        ('x1_5', '*1.5'),
        ('x1_75', '*1.75'),
        ('x2', '*2'),
        ('custom', 'مخصص'),
    ], string="الإجراء", required=True, default='x1')
    custom_value = fields.Float(string="مخصص", digits=(10, 2))
    special_time = fields.Boolean(string="توقيت خاص")
    special_time_value = fields.Float(string="التوقيت", widget='float_time')

    _sql_constraints = [
        ('type_category_special_unique',
         'UNIQUE(config_id, ot_type, ot_category, special_time)',
         'لا يمكن تكرار نفس النوع مع نفس الفئة مع نفس حالة التوقيت الخاص!'),
    ]


class LeadersitsHrTimeConfigLits(models.Model):
    _name = 'leadersits.hr.time.config.lits'
    _description = 'خطوط LITS'

    config_id = fields.Many2one(
        'leadersits.hr.time.config', string="الإعدادات",
        required=True, ondelete='cascade')
    name = fields.Char(string="البند", required=True)
    value = fields.Float(string="القيمة")
    description = fields.Char(string="ملاحظات")
