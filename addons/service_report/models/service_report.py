# models/service_report.py

import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ServiceReport(models.Model):
    _name = 'service.report'
    _description = 'Service Report'

    name = fields.Char('Report Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    transport_cost = fields.Float('Transport Cost')
    hotel_cost = fields.Float('Hotel Cost')
    machine_parts_cost = fields.Float('Machine Parts Cost')
    employee_services = fields.One2many('service.report.line', 'report_id', string="Employee Services")
    total_cost = fields.Float(string="Total Cost", compute="_compute_total", store=True)
    email = fields.Char("Accounting Email", required=True)
    client_signature = fields.Binary("Client Signature", help="Client signature image")
    signed = fields.Boolean(
        string="Signed by Client",
        compute="_compute_signed",
        store=True
    )

    @api.depends('transport_cost', 'hotel_cost', 'machine_parts_cost', 'employee_services.total_cost')
    def _compute_total(self):
        for record in self:
            line_total = sum(line.total_cost for line in record.employee_services)
            record.total_cost = record.transport_cost + record.hotel_cost + record.machine_parts_cost + line_total

    @api.depends('client_signature')
    def _compute_signed(self):
        for rec in self:
            rec.signed = bool(rec.client_signature)

    def action_send_pdf(self):
        """Send the service report PDF to the given accounting email."""
        self.ensure_one()
        if not self.signed:
            raise UserError(_("The report has not been signed by the client yet!"))

        # Generate PDF using the QWeb report
        report = self.env.ref('service_report.action_report_service_report_pdf')

        pdf_content, _ignored = report._render_qweb_pdf(self.ids)

        # Prepare the email with the PDF as an attachment
        mail_values = {
            'subject': _('Service Report - %s') % self.name,
            'body_html': _('<p>Please find attached the service report.</p>'),
            'email_to': self.email,
            'attachment_ids': [(0, 0, {
                'name': '%s.pdf' % self.name,
                'datas': base64.b64encode(pdf_content),
                'datas_fname': '%s.pdf' % self.name,
                'res_model': 'service.report',
                'res_id': self.id,
            })],
        }
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        return True

    def action_print(self):
        return (self.env.ref(
            'service_report.action_report_service_report_pdf')
        .report_action(self))

class ServiceReportLine(models.Model):
    _name = 'service.report.line'
    _description = 'Service Report Line'

    report_id = fields.Many2one('service.report', string='Service Report', required=True, ondelete='cascade')
    description = fields.Char("Service Description")
    quantity = fields.Float("Quantity")
    unit_cost = fields.Float("Unit Cost")
    total_cost = fields.Float(string="Total Cost", compute="_compute_total_cost", store=True)

    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = line.quantity * line.unit_cost


