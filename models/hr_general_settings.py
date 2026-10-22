from odoo import api, fields, models


class LeadersitsHrGeneralSettings(models.Model):
    _name = 'leadersits.hr.general.settings'
    _description = 'اعدادات عامة'

    name = fields.Char(default="اعدادات عامة")

    att_allow_create = fields.Boolean(string="اضافة", default=True)
    att_allow_edit = fields.Boolean(string="تعديل", default=True)
    att_allow_delete = fields.Boolean(string="حذف", default=True)
    att_kiosk_mode = fields.Boolean(string="وضع الكشك", default=True)

    @api.model
    def action_open_general_settings(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({'name': 'اعدادات عامة'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def write(self, vals):
        res = super().write(vals)
        if 'att_kiosk_mode' in vals:
            self._update_kiosk_menu()
        return res

    def _update_kiosk_menu(self):
        menu = self.env.ref(
            'hr_attendance.menu_action_open_form', raise_if_not_found=False)
        if menu:
            menu.sudo().write({'active': self.att_kiosk_mode})

    @api.model
    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute("""
            SELECT att_kiosk_mode FROM leadersits_hr_general_settings LIMIT 1
        """)
        row = self.env.cr.fetchone()
        if row:
            kiosk_enabled = row[0]
            self.env.cr.execute("""
                UPDATE ir_ui_menu SET active = %s
                WHERE id = (
                    SELECT res_id FROM ir_model_data
                    WHERE module = 'hr_attendance'
                    AND name = 'menu_action_open_form' LIMIT 1
                )
            """, (kiosk_enabled,))
        return res

    @api.model
    def get_settings(self):
        rec = self.search([], limit=1)
        if not rec:
            return {
                'att_allow_create': True,
                'att_allow_edit': True,
                'att_allow_delete': True,
            }
        return {
            'att_allow_create': rec.att_allow_create,
            'att_allow_edit': rec.att_allow_edit,
            'att_allow_delete': rec.att_allow_delete,
        }


