from odoo import api, fields, models
from datetime import date, timedelta


class LeadersitsHrDashboard(models.Model):
    _name = 'leadersits.hr.dashboard'
    _description = 'لوحة إحصائيات الموارد البشرية'

    name = fields.Char(default="لوحة الإحصائيات")

    # --- الموظفين ---
    total_employees = fields.Integer(compute='_compute_stats')
    active_employees = fields.Integer(compute='_compute_stats')
    archived_employees = fields.Integer(compute='_compute_stats')
    dept_count = fields.Integer(string="عدد الإدارات", compute='_compute_stats')

    # --- العقود ---
    active_contracts = fields.Integer(compute='_compute_stats')
    expiring_contracts = fields.Integer(compute='_compute_stats')
    expired_contracts = fields.Integer(compute='_compute_stats')

    # --- الحضور اليوم ---
    today_present = fields.Integer(compute='_compute_attendance')
    today_absent = fields.Integer(compute='_compute_attendance')
    today_records = fields.Integer(compute='_compute_attendance')

    # --- تحذيرات ---
    no_contract = fields.Integer(compute='_compute_warnings')
    no_code = fields.Integer(compute='_compute_warnings')
    no_badge = fields.Integer(compute='_compute_warnings')
    no_bank = fields.Integer(compute='_compute_warnings')

    def _compute_stats(self):
        Emp = self.env['hr.employee']
        Contract = self.env['hr.contract']
        Dept = self.env['hr.department']
        today = date.today()
        for rec in self:
            active = Emp.search_count([])
            archived = Emp.with_context(active_test=False).search_count(
                [('active', '=', False)])
            rec.active_employees = active
            rec.archived_employees = archived
            rec.total_employees = active + archived
            rec.dept_count = Dept.search_count([])
            rec.active_contracts = Contract.search_count([
                ('state', '=', 'open')])
            rec.expiring_contracts = Contract.search_count([
                ('state', '=', 'open'),
                ('date_end', '!=', False),
                ('date_end', '<=', today + timedelta(days=30)),
                ('date_end', '>=', today),
            ])
            rec.expired_contracts = Contract.search_count([
                ('state', '=', 'open'),
                ('date_end', '!=', False),
                ('date_end', '<', today),
            ])

    def _compute_attendance(self):
        Detail = self.env['leadersits.hr.attendance.detail']
        Emp = self.env['hr.employee']
        today = date.today()
        for rec in self:
            today_recs = Detail.search_count([('calc_date', '=', today)])
            present_emps = Detail.search([('calc_date', '=', today)])
            present_ids = present_emps.mapped('employee_id').ids
            total_active = Emp.search_count([])
            rec.today_records = today_recs
            rec.today_present = len(set(present_ids))
            rec.today_absent = max(0, total_active - rec.today_present)

    def _compute_warnings(self):
        Emp = self.env['hr.employee']
        Contract = self.env['hr.contract']
        for rec in self:
            all_emps = Emp.search([])
            has_contract_ids = Contract.search([
                ('state', '=', 'open')
            ]).mapped('employee_id').ids
            rec.no_contract = len(
                [e for e in all_emps if e.id not in has_contract_ids])
            rec.no_code = Emp.search_count([
                '|', ('lits_employee_code', '=', False),
                ('lits_employee_code', '=', '')])
            rec.no_badge = Emp.search_count([
                '|', ('lits_badge_number', '=', False),
                ('lits_badge_number', '=', '')])
            rec.no_bank = Emp.search_count([
                '|', ('lits_bank_account', '=', False),
                ('lits_bank_account', '=', '')])

    @api.model
    def action_open_dashboard(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({'name': 'لوحة الإحصائيات'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # --- أزرار الفتح ---
    def action_view_active_employees(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'الموظفين النشطين',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_view_archived_employees(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'الموظفين المؤرشفين',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('active', '=', False)],
            'context': {'active_test': False},
            'target': 'current',
        }

    def action_view_active_contracts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'العقود الجارية',
            'res_model': 'hr.contract',
            'view_mode': 'list,form',
            'domain': [('state', '=', 'open')],
            'target': 'current',
        }

    def action_view_expiring_contracts(self):
        today = date.today()
        return {
            'type': 'ir.actions.act_window',
            'name': 'عقود تنتهي خلال 30 يوم',
            'res_model': 'hr.contract',
            'view_mode': 'list,form',
            'domain': [
                ('state', '=', 'open'),
                ('date_end', '!=', False),
                ('date_end', '<=', str(today + timedelta(days=30))),
                ('date_end', '>=', str(today)),
            ],
            'target': 'current',
        }

    def action_view_expired_contracts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'عقود منتهية',
            'res_model': 'hr.contract',
            'view_mode': 'list,form',
            'domain': [
                ('state', '=', 'open'),
                ('date_end', '!=', False),
                ('date_end', '<', str(date.today())),
            ],
            'target': 'current',
        }

    def action_view_today_attendance(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'حضور اليوم',
            'res_model': 'leadersits.hr.attendance.detail',
            'view_mode': 'list,form',
            'domain': [('calc_date', '=', str(date.today()))],
            'target': 'current',
        }

    def action_view_no_contract(self):
        Contract = self.env['hr.contract']
        has_ids = Contract.search([
            ('state', '=', 'open')
        ]).mapped('employee_id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'موظفين بدون عقود جارية',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'not in', has_ids)],
            'target': 'current',
        }

    def action_view_no_code(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'موظفين بدون كود',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': ['|', ('lits_employee_code', '=', False),
                        ('lits_employee_code', '=', '')],
            'target': 'current',
        }

    def action_view_no_badge(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'موظفين بدون رقم تعريف',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': ['|', ('lits_badge_number', '=', False),
                        ('lits_badge_number', '=', '')],
            'target': 'current',
        }

    def action_view_no_bank(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'موظفين بدون حساب بنكي',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': ['|', ('lits_bank_account', '=', False),
                        ('lits_bank_account', '=', '')],
            'target': 'current',
        }

    def action_view_departments(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'الإدارات',
            'res_model': 'hr.department',
            'view_mode': 'list,form',
            'target': 'current',
        }
