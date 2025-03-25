# models/res_config_settings.py
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_accounting_email = fields.Char(
        string="Default Accounting Email",
        config_parameter='service_report.default_accounting_email',
        default_model='service.report',
    )
