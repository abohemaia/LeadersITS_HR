from odoo import fields, models


class HrWorkLocationLits(models.Model):
    _inherit = 'hr.work.location'

    lits_latitude = fields.Float(string="خط العرض", digits=(10, 7))
    lits_longitude = fields.Float(string="خط الطول", digits=(10, 7))
    lits_enabled = fields.Boolean(string="تفعيل", default=True)
