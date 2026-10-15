from odoo import fields, models


class LeadersItsHrFormTest(models.Model):
    _name = "leadersits.hr.form.test"
    _description = "FormTest"

    name = fields.Char(string="FormTest", default="FormTest")
