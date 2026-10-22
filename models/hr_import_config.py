from odoo import api, fields, models


class LeadersitsHrImportConfig(models.Model):
    _name = 'leadersits.hr.import.config'
    _description = 'إعدادات سحب بيانات الحضور والانصراف'

    name = fields.Char(default="إعدادات سحب البيانات")

    @api.model
    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute("""
            SELECT id, enable_excel, enable_database,
                   enable_fingerprint, enable_api
            FROM leadersits_hr_import_config LIMIT 1
        """)
        row = self.env.cr.fetchone()
        if row:
            menu_map = {
                1: 'menu_leadersits_hr_import_excel',
                2: 'menu_leadersits_hr_import_database',
                3: 'menu_leadersits_hr_import_fingerprint',
                4: 'menu_leadersits_hr_import_mobile',
            }
            for idx, xml_name in menu_map.items():
                enabled = row[idx]
                self.env.cr.execute("""
                    UPDATE ir_ui_menu SET active = %s
                    WHERE id = (
                        SELECT res_id FROM ir_model_data
                        WHERE module = 'LeadersITS_HR'
                        AND name = %s LIMIT 1
                    )
                """, (enabled, xml_name))
        return res

    # --- الجزء العلوي: Checkboxes ---
    enable_excel = fields.Boolean(string="اكسيل", default=True)
    enable_database = fields.Boolean(string="قواعد بيانات")
    enable_fingerprint = fields.Boolean(string="ماكينات بصمة")
    enable_api = fields.Boolean(string="ربط API")

    # --- Tab 1: قواعد بيانات ---
    db_server_type = fields.Selection([
        ('sqlserver', 'SQL Server'),
        ('oracle', 'Oracle'),
        ('access', 'Access'),
        ('sybase', 'Sybase'),
        ('mysql', 'MySQL'),
        ('postgree', 'PostgreSQL'),
        ('sqlite', 'SQLite'),
    ], string="نوع السيرفر")
    db_server_ip = fields.Char(string="السيرفر IP")
    db_name = fields.Char(string="قاعدة البيانات")
    db_user = fields.Char(string="المستخدم")
    db_password = fields.Char(string="كلمة المرور")
    db_table = fields.Char(string="الجدول")

    # --- Tab 2: ماكينات بصمة ---
    fingerprint_line_ids = fields.One2many(
        'leadersits.hr.import.config.fingerprint', 'config_id',
        string="ماكينات البصمة")

    # --- Tab 3: ربط API ---
    api_url = fields.Char(string="API")

    @api.model
    def action_open_import_config(self):
        config = self.search([], limit=1)
        if not config:
            config = self.create({'name': 'إعدادات سحب البيانات'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def write(self, vals):
        res = super().write(vals)
        self._update_menu_visibility()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._update_menu_visibility()
        return records

    def _update_menu_visibility(self):
        menu_map = {
            'enable_excel': 'LeadersITS_HR.menu_leadersits_hr_import_excel',
            'enable_database': 'LeadersITS_HR.menu_leadersits_hr_import_database',
            'enable_fingerprint': 'LeadersITS_HR.menu_leadersits_hr_import_fingerprint',
            'enable_api': 'LeadersITS_HR.menu_leadersits_hr_import_mobile',
        }
        for field_name, xml_id in menu_map.items():
            menu = self.env.ref(xml_id, raise_if_not_found=False)
            if menu:
                menu.sudo().write({'active': self[field_name]})


class LeadersitsHrImportConfigFingerprint(models.Model):
    _name = 'leadersits.hr.import.config.fingerprint'
    _description = 'ماكينات البصمة'

    config_id = fields.Many2one(
        'leadersits.hr.import.config', string="الإعدادات",
        required=True, ondelete='cascade')
    work_location_id = fields.Many2one(
        'hr.work.location', string="موقع العمل")
    machine_code = fields.Char(string="كود الماكينة")
    machine_ip = fields.Char(string="IP الماكينة")
    machine_direction = fields.Selection([
        ('all', 'الكل'),
        ('in', 'حضور'),
        ('out', 'انصراف'),
    ], string="اتجاه الماكينة", default='all', required=True)
