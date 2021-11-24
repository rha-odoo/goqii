# -*- coding: utf-8 -*-
{
    'name': "TeXByte GSTR reports",

    'summary': """
        GST module by TeXByte Solutions""",

    'description': """
        Enhances the Odoo accounting module with GST specific functions.
        Includes GSTR1, GSTR2 and GSTR3B reports and proper Reverse Charge handling.
    """,

    'author': "TeXByte Solutions",
    'website': "https://www.texbyte.in",
    'license': 'OPL-1',
    'support': 'info@texbyte.in',
    'price': 175,
    'currency': 'EUR',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['l10n_in'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'reports/view_report_gstr1.xml',
        'reports/view_report_gstr2.xml',
        'reports/view_report_gstr3b.xml',
        'reports/view_report_gstr9.xml',
        'data/account_fiscal_position.xml',
        'data/account_fiscal_position_account.xml',
        'data/account_chart_template_load_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        #'demo/demo.xml',
    ],
    'images': ['static/description/banner.png'],

    'installable':True,
    'application':True,
    'auto_install':False,
}
