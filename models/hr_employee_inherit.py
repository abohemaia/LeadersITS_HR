from odoo import fields, models


class HrEmployeeLits(models.Model):
    _inherit = "hr.employee"

    lits_employee_code = fields.Char(string="كود الموظف", copy=False)
    lits_badge_number = fields.Char(string="رقم البصمة")
    lits_whatsapp_mobile = fields.Char(string="Whatsapp Mobile")
    lits_bank_account = fields.Char(string="رقم الحساب البنكي")
    lits_bank_name = fields.Char(string="اسم البنك")

    _sql_constraints = [
        ('lits_employee_code_unique', 'UNIQUE(lits_employee_code)',
         'كود الموظف يجب أن يكون فريداً!'),
    ]
