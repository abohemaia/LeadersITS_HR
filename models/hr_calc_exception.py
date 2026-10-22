from odoo import api, fields, models

WORK_SYSTEM_EFFECTS = {
    'work_days':     {'eff_late': False, 'eff_leave_during': False, 'eff_early_leave': False, 'eff_morning_ot': False, 'eff_evening_ot': True,  'eff_absence': True,  'eff_punch_error': True,  'eff_location_error': True},
    'work_schedule': {'eff_late': True,  'eff_leave_during': True,  'eff_early_leave': True,  'eff_morning_ot': True,  'eff_evening_ot': True,  'eff_absence': True,  'eff_punch_error': True,  'eff_location_error': True},
    'daily_free':    {'eff_late': False, 'eff_leave_during': True,  'eff_early_leave': True,  'eff_morning_ot': False, 'eff_evening_ot': True,  'eff_absence': True,  'eff_punch_error': True,  'eff_location_error': True},
    'monthly_free':  {'eff_late': False, 'eff_leave_during': False, 'eff_early_leave': False, 'eff_morning_ot': False, 'eff_evening_ot': False, 'eff_absence': True,  'eff_punch_error': True,  'eff_location_error': True},
    'free_hours':    {'eff_late': False, 'eff_leave_during': False, 'eff_early_leave': False, 'eff_morning_ot': False, 'eff_evening_ot': False, 'eff_absence': False, 'eff_punch_error': True,  'eff_location_error': True},
    'consultant':    {'eff_late': False, 'eff_leave_during': False, 'eff_early_leave': False, 'eff_morning_ot': False, 'eff_evening_ot': False, 'eff_absence': False, 'eff_punch_error': False, 'eff_location_error': False},
}

EFFECT_FIELDS = [
    'eff_late', 'eff_leave_during', 'eff_early_leave',
    'eff_morning_ot', 'eff_evening_ot', 'eff_absence',
    'eff_punch_error', 'eff_location_error',
]


class LeadersitsHrCalcException(models.Model):
    _name = 'leadersits.hr.calc.exception'
    _description = 'استثناءات اجراء الحساب'
    _order = 'date_from desc'

    target_type = fields.Selection([
        ('employee', 'الموظف'),
        ('department', 'القسم'),
        ('job', 'الوظيفة'),
    ], string="الوضع", required=True, default='employee')

    employee_ids = fields.Many2many(
        'hr.employee', string="الموظف",
        relation='hr_calc_exception_employee_rel')
    department_ids = fields.Many2many(
        'hr.department', string="القسم",
        relation='hr_calc_exception_dept_rel')
    job_ids = fields.Many2many(
        'hr.job', string="الوظيفة",
        relation='hr_calc_exception_job_rel')

    lits_work_system = fields.Selection([
        ('work_days', 'أيام عمل'),
        ('work_schedule', 'مواعيد عمل'),
        ('daily_free', 'حرة يومية'),
        ('monthly_free', 'حرة شهرية'),
        ('free_hours', 'ساعات حرة'),
        ('consultant', 'استشاري'),
    ], string="نظام العمل", required=True)

    eff_late = fields.Boolean(string="التأخير")
    eff_leave_during = fields.Boolean(string="خروج وقت العمل")
    eff_early_leave = fields.Boolean(string="خروج مبكر")
    eff_morning_ot = fields.Boolean(string="إضافي صباحي")
    eff_evening_ot = fields.Boolean(string="إضافي مسائي")
    eff_absence = fields.Boolean(string="غياب")
    eff_punch_error = fields.Boolean(string="خطأ بصمة")
    eff_location_error = fields.Boolean(string="خطأ الموقع")

    date_from = fields.Date(string="من تاريخ", required=True)
    date_to = fields.Date(string="إلى تاريخ", required=True)
    reason = fields.Char(string="السبب")

    @api.onchange('target_type')
    def _onchange_target_type(self):
        if self.target_type != 'employee':
            self.employee_ids = [(5,)]
        if self.target_type != 'department':
            self.department_ids = [(5,)]
        if self.target_type != 'job':
            self.job_ids = [(5,)]

    @api.onchange('lits_work_system')
    def _onchange_lits_work_system(self):
        effects = WORK_SYSTEM_EFFECTS.get(self.lits_work_system, {})
        if not effects:
            return

        if self._origin and self._origin.lits_work_system == self.lits_work_system:
            for field_name in EFFECT_FIELDS:
                setattr(self, field_name, getattr(self._origin, field_name))
            return

        for field_name, enabled in effects.items():
            setattr(self, field_name, enabled)
