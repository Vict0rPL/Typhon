import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import AccessError


class ServiceReport(models.Model):
    _name = 'service.report'
    _description = 'Service Report'
    # Check role
    is_not_manager = fields.Boolean(compute='_compute_is_not_manager', store=False)
    # General
    name = fields.Char('Report Reference', required=True, copy=False, default=lambda self: _('New Report'))
    employee_id = fields.Many2one('res.users', string="Employee", required=True)
    location = fields.Many2one('res.partner', string="Service Location", required=True)
    service_date = fields.Date('Service Date')
    service_description = fields.Text("Service Description")
    accounting_email = fields.Char("Accounting Email", required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    # Travel
    travel_details = fields.One2many('service.report.travel_line', 'report_id', string="Travel Details")
    transport_cost = fields.Float('Transport Cost')
    hotel_cost = fields.Float('Hotel Cost')
    # Work Details
    employee_services = fields.One2many('service.report.work_line', 'report_id', string="Employee Services")
    # Parts Used
    parts_used = fields.One2many('service.report.part_line', 'report_id', string="Parts Used")
    machine_parts_cost = fields.Float(string="Machine Parts Cost", compute="_compute_parts_cost", store=True)
    # Summary
    total_work_time = fields.Float(string="Total Work Time", compute="_compute_total_time", store=True)
    total_cost = fields.Float(string="Total Cost", compute="_compute_total_cost", store=True)
    # Client Data and Signature
    client_email = fields.Char("Client Email")
    client_signature = fields.Binary("Client Signature", help="Client signature image")
    signed = fields.Boolean(string="Signed by Client", compute="_compute_signed", store=True)

    @api.depends('travel_details.time', 'employee_services.time')
    def _compute_total_time(self):
        for record in self:
            travel_line_total = sum(line.time for line in record.employee_services)
            services_line_total = sum(line.time for line in record.travel_details)
            record.total_work_time = travel_line_total + services_line_total

    @api.depends('transport_cost', 'hotel_cost', 'machine_parts_cost', 'parts_used.total_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.transport_cost + record.hotel_cost + record.machine_parts_cost

    @api.depends('parts_used.total_cost')
    def _compute_parts_cost(self):
        for record in self:
            part_line_total = sum(line.total_cost for line in record.parts_used)
            record.machine_parts_cost = part_line_total

    @api.depends('client_signature')
    def _compute_signed(self):
        for rec in self:
            rec.signed = bool(rec.client_signature)

    @api.model
    def create(self, vals):
        if not self.env.user.has_group('service_report.group_service_manager'):
            raise AccessError(_("Only managers can create service reports."))
        if not vals.get('accounting_email'):
            # Get from config parameter if not set manually
            default_email = self.env['ir.config_parameter'].sudo().get_param('service_report.default_accounting_email')
            vals['accounting_email'] = default_email
        return super().create(vals)

    def unlink(self):
        if not self.env.user.has_group('service_report.group_service_manager'):
            raise AccessError(_("Only managers can delete service reports."))
        return super().unlink()

    def _compute_is_not_manager(self):
        is_manager = self.env.user.has_group('service_report.group_service_manager')
        for record in self:
            record.is_not_manager = not is_manager

    def write(self, vals):
        restricted_fields = {
            'name', 'service_description', 'employee_id', 'location', 'service_date', 'accounting_email'
        }
        if not self.env.user.has_group('service_report.group_service_manager'):
            if restricted_fields & set(vals):
                raise AccessError(_("Only managers can modify general service fields."))
        return super().write(vals)

    def action_send_pdf(self):
        """Send the service report PDF to the given accounting email."""
        self.ensure_one()
        if not self.signed:
            raise UserError(_("The report has not been signed by the client yet!"))

        # Generate PDF
        pdf_content, _ignored = self.env['ir.actions.report']._render_qweb_pdf(
            'service_report.action_report_service_report_pdf', self.id
        )

        # Prepare and send email
        mail_values = {
            'subject': _('Service Report - %s') % self.name,
            'body_html': _('<p>Please find attached the service report.</p>'),
            'email_to': self.accounting_email,
            'attachment_ids': [(0, 0, {
                'name': '%s.pdf' % self.name,
                'datas': base64.b64encode(pdf_content).decode(),  # convert bytes to str
                'res_model': 'service.report',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })],
        }
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        return True

    def action_print(self):
        return (self.env.ref(
            'service_report.action_report_service_report_pdf')
        .report_action(self))


class ServiceReportTravelLine(models.Model):
    _name = 'service.report.travel_line'
    _description = 'Service Report Travel Line'

    report_id = fields.Many2one('service.report', string='Service Report', required=True, ondelete='cascade')
    start_location = fields.Char("Start Location")
    end_location = fields.Char("End Location")
    start_time = fields.Float("Start Time (HH.MM)", help="Use 24-hour format, e.g., 14.5 for 14:30")
    end_time = fields.Float("End Time (HH.MM)", help="Use 24-hour format, e.g., 16.25 for 16:15")
    time = fields.Float("Travel Time (Hours)", compute="_compute_travel_time", store=True)
    distance = fields.Float("Distance")
    date = fields.Date('Travel Date')

    @api.depends('start_time', 'end_time')
    def _compute_travel_time(self):
        for record in self:
            if record.start_time is not None and record.end_time is not None:
                record.time = max(record.end_time - record.start_time, 0.0)
            else:
                record.time = 0.0


class ServiceReportWorkLine(models.Model):
    _name = 'service.report.work_line'
    _description = 'Service Report Work Line'

    report_id = fields.Many2one('service.report', string='Service Report', required=True, ondelete='cascade')
    description = fields.Char("Work Description")
    start_time = fields.Float("Start Time (HH.MM)", help="Use 24-hour format, e.g., 14.5 for 14:30")
    end_time = fields.Float("End Time (HH.MM)", help="Use 24-hour format, e.g., 16.25 for 16:15")
    time = fields.Float("Work Time (Hours)", compute="_compute_work_time", store=True)

    @api.depends('start_time', 'end_time')
    def _compute_work_time(self):
        for record in self:
            if record.start_time is not None and record.end_time is not None:
                record.time = max(record.end_time - record.start_time, 0.0)
            else:
                record.time = 0.0


class ServiceReportPartLine(models.Model):
    _name = 'service.report.part_line'
    _description = 'Service Report Part Line'

    report_id = fields.Many2one('service.report', string='Service Report', required=True, ondelete='cascade')
    description = fields.Char("Part Description")
    quantity = fields.Float("Quantity")
    unit_cost = fields.Float("Unit Cost")
    total_cost = fields.Float(string="Total Cost", compute="_compute_line_cost", store=True)

    @api.depends('quantity', 'unit_cost')
    def _compute_line_cost(self):
        for line in self:
            line.total_cost = line.quantity * line.unit_cost
