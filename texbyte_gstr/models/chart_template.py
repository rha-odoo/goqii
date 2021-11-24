#  vim:ts=8:sts=4:sw=4:tw=0:et:si:fileencoding=utf-8:
# -*- coding: utf-8 -*-
# This file is part of TeXByte GST module. See LICENSE for details

from odoo import models, fields, api
import odoo.addons.decimal_precision as dp

import logging
_logger = logging.getLogger(__name__)
import pdb


''' Account Chart Template '''
class TeXByteInvoice(models.Model):
    _inherit = 'account.chart.template'

    #Load fiscal position, tax & account mapping from templates (to create entries for current company)
    #Adapted from account.chart.template:_load_template()
    def try_loading_fpos_for_current_company(self):
        #pdb.set_trace()
        self.ensure_one()
        company_id = self.env.user.company_id
        account_ref = {}
        taxes_ref = {}
        generated_tax_res = {}
        code_digits = self.code_digits
        AccountTaxObj = self.env['account.tax']

        #Restrict loading tax, accounts and fiscal position only to entries in *this module*

        #Get the templates with XMLID stored by this module
        module_templates = self.env['ir.model.data'].search_read([('module','=',self._module), ('model','like', '%template')],
                ['noupdate', 'name', 'model', 'res_id'], order="model")
        # Generate taxes from templates.
        tax_templ_ids = list(map(lambda n: n.get('res_id'), filter(lambda l: l.get('model') == 'account.tax.template', module_templates)))
        if len(tax_templ_ids):
            tax_templates = self.env['account.tax.template'].browse(tax_templ_ids)
            generated_tax_res = tax_templates._generate_tax(company_id)
            taxes_ref.update(generated_tax_res['tax_template_to_tax'])

        # Generating Accounts from templates.
        acc_templ_ids =  list(map(lambda n: n.get('res_id'), filter(lambda l: l.get('model') == 'account.account.template', module_templates)))
        if len(acc_templ_ids):
            account_template_ref = self.generate_selected_account(acc_templ_ids, taxes_ref, account_ref, code_digits, company_id)
            account_ref.update(account_template_ref)

            # writing account values after creation of accounts
            if generated_tax_res:
                for key, value in generated_tax_res['account_dict'].items():
                    if value['refund_account_id'] or value['account_id'] or value['cash_basis_account']:
                        AccountTaxObj.browse(key).write({
                            'refund_account_id': account_ref.get(value['refund_account_id'], False),
                            'account_id': account_ref.get(value['account_id'], False),
                            'cash_basis_account': account_ref.get(value['cash_basis_account'], False),
                        })

        #Need info of all existing taxes (in inheriting/extending module) and accounts template:real model mapping, fill those
        parent_module = self.env['ir.model.data'].search([('res_id','=',self.id), ('model','=',self._name)])[0].module    #'l10n_in'
        exist_tax_templs = self.env['ir.model.data'].search_read([('module','=',parent_module),('model','=','account.tax.template')], ['name','res_id'])
        exist_real_taxes = self.env['ir.model.data'].search_read([('module','=',parent_module),('model','=','account.tax'),('name','like',str(company_id.id)+'_%')], ['name','res_id'])
        for templ in exist_tax_templs:
            obj_name = str(company_id.id) + '_' + templ.get('name')
            real_id = list(map(lambda n: n.get('res_id'), filter(lambda l: l.get('name') == obj_name, exist_real_taxes)))
            if len(real_id):
                taxes_ref.update({ templ.get('res_id'): real_id[0]})

        exist_acc_templs = self.env['ir.model.data'].search_read([('module','=',parent_module),('model','=','account.account.template')], ['name','res_id'])
        exist_real_accs = self.env['ir.model.data'].search_read([('module','=',parent_module),('model','=','account.account'),('name','like',str(company_id.id)+'_%')], ['name','res_id'])
        for templ in exist_acc_templs:
            obj_name = str(company_id.id) + '_' + templ.get('name')
            real_id = list(map(lambda n: n.get('res_id'), filter(lambda l: l.get('name') == obj_name, exist_real_accs)))
            if len(real_id):
                account_ref.update({ templ.get('res_id'): real_id[0]})


        # Generate Fiscal Position , Fiscal Position Accounts and Fiscal Position Taxes from templates
        fpos_templ_ids =  list(map(lambda n: n.get('res_id'), filter(lambda l: l.get('model') == 'account.fiscal.position.template', module_templates)))
        if len(fpos_templ_ids):
            self.generate_selected_fiscal_position(fpos_templ_ids, taxes_ref, account_ref, company_id)


    def generate_selected_account(self, acc_template_ids, tax_template_ref, acc_template_ref, code_digits, company):
        """ This method for generating accounts from templates.

            :param acc_template_ids: List of Account template ids for which real accounts are created.
            :param tax_template_ref: Taxes templates reference for write taxes_id in account_account.
            :param acc_template_ref: dictionary with the mappping between the account templates and the real accounts.
            :param code_digits: number of digits got from wizard.multi.charts.accounts, this is use for account code.
            :param company_id: company_id selected from wizard.multi.charts.accounts.
            :returns: return acc_template_ref for reference purpose.
            :rtype: dict
        """
        self.ensure_one()
        acc_templates = self.env['account.account.template'].browse(acc_template_ids)
        for account_template in acc_templates:
            code_main = account_template.code and len(account_template.code) or 0
            code_acc = account_template.code or ''
            if code_main > 0 and code_main <= code_digits:
                code_acc = str(code_acc) + (str('0'*(code_digits-code_main)))
            vals = self._get_account_vals(company, account_template, code_acc, tax_template_ref)
            new_account = self.create_record_with_xmlid(company, account_template, 'account.account', vals)
            acc_template_ref[account_template.id] = new_account
        return acc_template_ref


    def generate_selected_fiscal_position(self, fpos_template_ids, tax_template_ref, acc_template_ref, company):
        """ This method generate Fiscal Position, Fiscal Position Accounts and Fiscal Position Taxes from templates.

            :param fpos_template_ids: List of Fiscal position tempate ids for which real fiscal positions are created.
            :param chart_temp_id: Chart Template Id.
            :param taxes_ids: Taxes templates reference for generating account.fiscal.position.tax.
            :param acc_template_ref: Account templates reference for generating account.fiscal.position.account.
            :param company_id: company_id selected from wizard.multi.charts.accounts.
            :returns: True
        """
        self.ensure_one()
        fpos_templates = self.env['account.fiscal.position.template'].browse(fpos_template_ids)
        for position in fpos_templates:
            fp_vals = self._get_fp_vals(company, position)
            new_fp = self.create_record_with_xmlid(company, position, 'account.fiscal.position', fp_vals)
            #NOTE: it is entirely possible that some users may have deleted standard taxes & accounts. Check if the expected taxes & accounts exist
            for tax in position.tax_ids:
                if tax_template_ref.get(tax.tax_src_id.id, False) and tax_template_ref.get(tax.tax_dest_id.id, False):
                    self.create_record_with_xmlid(company, tax, 'account.fiscal.position.tax', {
                        'tax_src_id': tax_template_ref[tax.tax_src_id.id],
                        'tax_dest_id': tax.tax_dest_id and tax_template_ref[tax.tax_dest_id.id] or False,
                        'position_id': new_fp
                    })
            for acc in position.account_ids:
                if acc_template_ref.get(acc.account_src_id.id, False) and acc_template_ref.get(acc.account_dest_id.id, False):
                    self.create_record_with_xmlid(company, acc, 'account.fiscal.position.account', {
                        'account_src_id': acc_template_ref[acc.account_src_id.id],
                        'account_dest_id': acc_template_ref[acc.account_dest_id.id],
                        'position_id': new_fp
                    })
        return True
