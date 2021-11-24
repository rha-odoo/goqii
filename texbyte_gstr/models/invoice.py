#  vim:ts=8:sts=4:sw=4:tw=0:et:si:fileencoding=utf-8 :
# -*- coding: utf-8 -*-
# This file is part of TeXByte GST module. See LICENSE for details

from odoo import models, fields, api
import odoo.addons.decimal_precision as dp

import logging
_logger = logging.getLogger(__name__)
import pdb


''' Account Invoice '''
class GSTInvoice(models.Model):
    _inherit = 'account.move'


    ''' Methods '''
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        #Remove tax lines, after fiscal position is set, recompute the tax lines
        #pdb.set_trace()
        result = super(GSTInvoice, self)._onchange_partner_id()
        self.line_ids = self.invoice_line_ids
        self._onchange_fiscal_position_id()
        self._recompute_dynamic_lines(recompute_all_taxes=True)
        #self._recompute_tax_lines()
        return result


    """ Ensure to reapply taxes on lines when fiscal position changes """
    @api.onchange('fiscal_position_id')
    def _onchange_fiscal_position_id(self):
        #pdb.set_trace()
        #_logger.info(self.fiscal_position_id and self.fiscal_position_id.name)
        for line in self.invoice_line_ids:
            #_logger.info(line.tax_ids and line.tax_ids.name)
            line.tax_ids = line._get_computed_taxes()
            #_logger.info(line.tax_ids and line.tax_ids.name)


    def _is_reverse_charge_applicable(self):
        if self.move_type in ('in_invoice', 'in_refund') and self.partner_id and not self.partner_id.vat and not self.l10n_in_gst_treatment == 'overseas':
            return True
        else:
            return False


    def _recompute_tax_lines(self, recompute_tax_base_amount=False):
        # OVERRID the parent method to add reverse charge tax lines (for each tax line, add reversed amount on mapped account)
        self.ensure_one()
        in_draft_mode = self != self._origin

        #Remove all tax lines
        #for tax_line in self.line_ids.filtered(lambda l: l.tax_line_id):
        #    tax_line.unlink()

        super(GSTInvoice, self)._recompute_tax_lines(recompute_tax_base_amount)

        if not self._is_reverse_charge_applicable():
            return

        rev_charge_fpos = self.env['account.fiscal.position'].search([('name', 'like', 'Reverse Charge'), ('active', '=', True)], limit=1)
        if not rev_charge_fpos:
            return

        create_method = in_draft_mode and self.env['account.move.line'].new or self.env['account.move.line'].create

        AccountTag = self.env['account.account.tag']
        for tax_line in self.line_ids.filtered(lambda l: l.tax_line_id):
            rev_charge_tax_line_data = tax_line.copy_data()[0]
            #_logger.info(rev_charge_tax_line_data)
            rev_charge_tax_line_data['account_id'] = rev_charge_fpos.map_account(tax_line.account_id).id
            rev_charge_tax_line_data['debit'] = tax_line.credit
            rev_charge_tax_line_data['credit'] = tax_line.debit
            rev_tag_ids = []
            for tag in tax_line.tax_tag_ids:
                rev_tag_name = tag.name.replace('+','-') if tag.name.startswith('+') else tag.name.replace('-','+')
                rev_tag_ids.append(AccountTag.search([('name', '=', rev_tag_name)], limit=1)[0].id)
            rev_charge_tax_line_data['tax_tag_ids'] = [(6, 0, rev_tag_ids)]     #Replace the tag ids with reversed ones

            rev_charge_tax_line = create_method( rev_charge_tax_line_data )

            if in_draft_mode:
                rev_charge_tax_line._onchange_balance()

        #Sometimes, there's a rounding error
        #pdb.set_trace()
        #self._compute_amount()
