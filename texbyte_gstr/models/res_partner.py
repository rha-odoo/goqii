#  vim:ts=8:sts=4:sw=4:tw=0:et:si:fileencoding=utf-8 :
# -*- coding: utf-8 -*-
# This file is part of TeXByte GST module. See LICENSE for details

from odoo import models, fields, api
import odoo.addons.decimal_precision as dp

import logging
_logger = logging.getLogger(__name__)
import pdb


""" Partner """
class TeXBytePartner(models.Model):
    _inherit = 'res.partner'

    #Set customers Inter-state fiscal position automatically
    @api.onchange('state_id')
    def _onchange_state_id(self):
        #Interstate customer
        fpos_interstate = self.env['account.fiscal.position'].search([('name', '=', 'Inter State')], limit=1)[0]
        company_id = self.company_id or self.env.user.company_id
        if self.state_id and (self.country_id and self.country_id == company_id.country_id or True) and self.state_id != company_id.state_id:
            self.property_account_position_id = fpos_interstate
        elif self.property_account_position_id == fpos_interstate:
            self.property_account_position_id = False

    #Set Export fiscal position automatically
    @api.onchange('country_id')
    def _onchange_country_id(self):
        result = super(TeXBytePartner, self)._onchange_country_id()
        #Export to ouside country
        comp_country_id = self.company_id.country_id or self.env.user.company_id.country_id
        fpos_export = self.env['account.fiscal.position'].search([('name', '=', 'Export')], limit=1)[0]
        if self.country_id and self.country_id != comp_country_id:
            self.property_account_position_id = fpos_export
        elif self.property_account_position_id == fpos_export:
            self.property_account_position_id = False
            self._onchange_state_id()

        return result
