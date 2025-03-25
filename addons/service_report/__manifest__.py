{
    'name': 'Service Report',
    'version': '17.0.1.0.0',
    'category': 'Services',
    'summary': 'Create service reports including transport, hotel, machine parts, employee work, and totals. Generates a signed PDF emailed to accounting.',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/service_report_security.xml',
        'security/service_report_rules.xml',
        'security/ir.model.access.csv',
        'views/service_report_views.xml',
        'views/service_report_templates.xml',
        'data/email_template.xml',
    ],
    'installable': True,
    'application': True,
}
