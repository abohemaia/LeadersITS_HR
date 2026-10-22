from odoo import api, fields, models


class LeadersitsHrLocationException(models.Model):
    _name = 'leadersits.hr.location.exception'
    _description = 'استثناءات مواقع العمل'
    _order = 'date_from desc'

    target_type = fields.Selection([
        ('employee', 'الموظف'),
        ('department', 'القسم'),
        ('job', 'الوظيفة'),
    ], string="الوضع", required=True, default='employee')

    employee_ids = fields.Many2many(
        'hr.employee', string="الموظف",
        relation='hr_location_exception_employee_rel')
    department_ids = fields.Many2many(
        'hr.department', string="القسم",
        relation='hr_location_exception_dept_rel')
    job_ids = fields.Many2many(
        'hr.job', string="الوظيفة",
        relation='hr_location_exception_job_rel')

    work_location_id = fields.Many2one(
        'hr.work.location', string="موقع العمل", required=True)
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
