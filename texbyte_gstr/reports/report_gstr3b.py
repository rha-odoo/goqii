# This file is part of TeXByte GST module. See LICENSE for details
from odoo import fields, models, api, _

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import float_is_zero, float_compare
import xlwt
import base64
from io import BytesIO
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)

import pdb

B2CL_INVOICE_AMT_LIMIT = 250000

class GSTR3BReport(models.TransientModel):

    _name = 'texbyte_gstr.report.gstr3b'

    # fields to generate xls
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To')
    #inv_type = fields.Selection([('cust_inv','Sales Invoice'),('vndr_bil','Purchase Invoice')],
    #                            default='cust_inv')

    # fields for download xls
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],
                             default='choose')
    report = fields.Binary('Prepared file', filters='.xls', readonly=True)
    filename = fields.Char('File Name', size=128)

    all_invoices = []
    sorted_invoices = []
    refund_invoices = []
    canceled_invoices = []

    def get_valid_invoices(self):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        # Searching for customer invoices
        from_date = self.date_from
        to_date = self.date_to
        refund_invoice_ids = []

        #Get all invoices including canceled, refund and refunded
        all_invoices = self.env['account.move'].search([('invoice_date','>=', from_date),('invoice_date','<=', to_date), ('state','!=','draft')])   #Customer Invoice & Vendor Bills
        #Canceled invoices
        canceled_invoices = all_invoices.filtered(lambda i: i.state == 'cancel')
        #Refund invoices
        refund_invoices = all_invoices.filtered(lambda i: i.state != 'cancel' and i.move_type in ('out_refund', 'in_refund'))  # Skip canceled refunds
        # Legitimate invoices -- other than canceled and refund
        invoices = all_invoices.filtered(
            lambda i: i.id not in canceled_invoices.ids + refund_invoices.ids)
        sorted_invoices = invoices.sorted(key=lambda p: (p.invoice_date, p.name))


    def generate_gstr3b_report(self):
        #Error handling is not taken into consideraion
        self.ensure_one()
        fp = BytesIO()
        xl_workbook = xlwt.Workbook(encoding='utf-8')

        from_date = self.date_from
        to_date = self.date_to

        # Get the invoices
        self.get_valid_invoices()

        self.generate_3b_report(xl_workbook)

        xl_workbook.save(fp)

        out = base64.encodebytes(fp.getvalue())
        self.write({'state': 'choose', 'report': out, 'filename':'gstr3b_'+str(from_date)+'-'+str(to_date)+'.xls'})
        return {
            'name': 'GSTR3B',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=texbyte_gstr.report.gstr3b&id=" + str(self.id) + "&filename_field=filename&field=report&download=true&filename=" + self.filename,
            'target': 'current',
        }


    """ GSTR-3B Summary """
    def generate_3b_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        #Error handling is not taken into consideraion
        self.ensure_one()

        ws1 = wb1.add_sheet('GSTR-3B')
        fp = BytesIO()

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 12 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, col+1, col+6, "GSTR-3B", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "GSTIN", sub_header_style)
        ws1.write(row, col + 2, self.env.user.company_id.vat, sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Legal name of the registered person", sub_header_style)
        ws1.write(row, col + 2, self.env.user.company_id.name, sub_header_content_style)

        outward_taxable_supplies = {'taxable_value': 0.0, 'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        outward_taxable_zero_rated = {'taxable_value': 0.0, 'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        outward_taxable_exempted = {'taxable_value': 0.0, 'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        outward_non_gst = {'taxable_value': 0.0, 'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        inward_reverse_charge = {'taxable_value': 0.0, 'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        import_goods = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        import_service = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        inward_isd = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        all_itc = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        itc_reversed_1 = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        itc_reversed_2 = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        ineligible_1 = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        ineligible_2 = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        inward_zero_gst = {'inter': 0.0, 'intra': 0.0}
        non_gst = {'inter': 0.0, 'intra': 0.0}
        interest = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        pos_unreg_comp_uin_igst = {}     #{PoS: Unreg_Taxable_Amt, Unreg_IGST, Composition_Taxable_Amt, Composition_IGST, UIN_Taxamble_Amt, UIN_IGST}

        for invoice in sorted_invoices + refund_invoices:     #Net payable taxable + tax, subtracting credit notes
            sign = 1
            if invoice.move_type in ('out_refund', 'in_refund'):
                sign = -1

            foreign_curr = None
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                foreign_curr = invoice.currency_id
                curr_rate_date = invoice.date or invoice.invoice_date
                company_curr = invoice.company_id.currency_id

            for invoice_line in invoice.invoice_line_ids:
                prod_id = invoice_line.product_id
                if not prod_id:
                    continue
                line_uom = invoice_line.product_uom_id
                line_qty = line_uom._compute_quantity(invoice_line.quantity, prod_id and prod_id.uom_id or line_uom)
                # Take care of currency conversion
                line_amount = foreign_curr._convert(invoice_line.price_subtotal, company_curr, invoice.company_id, curr_rate_date) \
                    if foreign_curr else invoice_line.price_subtotal
                line_total_amount = foreign_curr._convert(invoice_line.price_total,company_curr, invoice.company_id, curr_rate_date) \
                    if foreign_curr else invoice_line.price_total
                price = invoice_line.price_unit * (1 - (invoice_line.discount or 0.0) / 100.0)
                line_taxes = invoice_line.tax_ids.compute_all(price, invoice.currency_id, invoice_line.quantity,
                                                            invoice_line.product_id, invoice.partner_id)
                # _logger.info(line_taxes)
                if foreign_curr:
                    line_taxes['total_excluded'] = foreign_curr._convert(line_taxes['total_excluded'], company_curr, invoice.company_id, curr_rate_date)
                    line_taxes['total_included'] = foreign_curr._convert(line_taxes['total_included'], company_curr, invoice.company_id, curr_rate_date)
                    for l in line_taxes['taxes']:
                        l['amount'] = foreign_curr._convert(l['amount'], company_curr, invoice.company_id, curr_rate_date)
                        l['base']   = foreign_curr._convert(l['base'], company_curr, invoice.company_id, curr_rate_date)

                # +ve for customer invoice, -ve for credit note
                line_amount                  *= sign
                line_total_amount            *= sign
                line_taxes['total_excluded'] *= sign
                line_taxes['total_included'] *= sign
                for l in line_taxes['taxes']:
                    l['amount'] *= sign

                #_logger.info(line_taxes)
                igst_amount = cgst_amount = sgst_amount = cess_amount = 0.0
                for tax_line in line_taxes['taxes']:
                    #tax_obj = self.env['account.tax'].browse(tax_line['id'])
                    if 'IGST' in tax_line['name']:   #tax_obj.gst_type == 'igst':
                        igst_amount += tax_line['amount']
                    elif 'CGST' in tax_line['name']: #tax_obj.gst_type == 'cgst':
                        cgst_amount += tax_line['amount']
                    elif 'SGST' in tax_line['name'] or 'UTGST' in tax_line['name']: #tax_obj.gst_type == 'sgst':
                        sgst_amount += tax_line['amount']
                    else:
                        cess_amount += tax_line['amount']

                #cgst_amount = invoice_line.tax_ids.filtered(lambda r: r.gst_type == 'cgst').amount
                #sgst_amount = invoice_line.tax_ids.filtered(lambda r: r.gst_type == 'sgst').amount
                #_logger.info(invoice_line.tax_ids)
                if invoice.move_type in ('out_invoice', 'out_refund'):       #Customer Invoice
                    if float_compare(line_total_amount, line_amount, precision_digits=2) != 0:   #Taxable item, not zero rated/nil rated/exempted
                       outward_taxable_supplies['taxable_value'] += line_amount
                       outward_taxable_supplies['igst'] += igst_amount
                       outward_taxable_supplies['cgst'] += cgst_amount
                       outward_taxable_supplies['sgst'] += sgst_amount
                       outward_taxable_supplies['cess'] += cess_amount
                       place_of_supply = invoice.partner_id.state_id.id or invoice.company_id.state_id.id
                       if pos_unreg_comp_uin_igst.get(place_of_supply):
                           pos_unreg_comp_uin_igst[place_of_supply]['unreg_taxable_amt'] += line_amount
                           pos_unreg_comp_uin_igst[place_of_supply]['unreg_igst'] += igst_amount
                       else:
                           pos_unreg_comp_uin_igst[place_of_supply] = {'unreg_taxable_amt': line_amount, 'unreg_igst': igst_amount,
                                                                                'comp_taxable_amt': 0, 'comp_igst': 0,
                                                                                'uin_taxable_amt': 0, 'uin_igst': 0}    #TODO: Handle Composition & UIN holders

                    else:                                                    #Tream them all as zero rated for now
                       outward_taxable_zero_rated['taxable_value'] += line_amount
                       outward_taxable_zero_rated['igst'] += igst_amount
                       outward_taxable_zero_rated['cgst'] += cgst_amount
                       outward_taxable_zero_rated['sgst'] += sgst_amount
                       outward_taxable_zero_rated['cess'] += cess_amount

                #TODO: Vendor Bills with reverse charge doesn't have tax lines filled, so it must be calculated
                elif invoice.move_type in ('in_invoice', 'in_refund'): #and invoice._is_reverse_charge_applicable(): #Vendor Bills with Reverse Charge applicablle
                    if invoice._is_reverse_charge_applicable():
                        inward_reverse_charge['taxable_value'] += line_amount
                        inward_reverse_charge['igst'] += igst_amount
                        inward_reverse_charge['cgst'] += cgst_amount
                        inward_reverse_charge['sgst'] += sgst_amount
                        inward_reverse_charge['cess'] += cess_amount
                    elif invoice.l10n_in_gst_treatment == 'overseas':     #Import vendor bill
                        import_goods_or_service = import_service if prod_id.type == 'service' else import_goods
                        import_goods_or_service['igst'] += igst_amount
                        import_goods_or_service['cgst'] += cgst_amount
                        import_goods_or_service['sgst'] += sgst_amount
                        import_goods_or_service['cess'] += cess_amount
                    else:
                        if float_compare(line_total_amount, line_amount, precision_digits=2) == 0:  #Zero GST taxes
                            if invoice.partner_id.state_id and invoice.partner_id.state_id != invoice.company_id.state_id:
                                inward_zero_gst['inter'] += line_amount
                            else:
                                inward_zero_gst['intra'] += line_amount
                        else:   #Taxable purchase, eligible for ITC
                            all_itc['igst'] += igst_amount
                            all_itc['cgst'] += cgst_amount
                            all_itc['sgst'] += sgst_amount

        row += 2

        #Inner functions
        def prepare_outward_supplies(row):
            ws1.write_merge(row, row, col+1, col+6, "3.1 Details of Outward Supplies and inward supplies liable to reverse charge", sub_header_style)
            row += 1
            ws1.write(row, col + 1, "Nature of Supplies", sub_header_style)
            ws1.write(row, col + 2, "Taxable Value", sub_header_style)
            ws1.write(row, col + 3, "IGST", sub_header_style)
            ws1.write(row, col + 4, "CGST", sub_header_style)
            ws1.write(row, col + 5, "SGST", sub_header_style)
            ws1.write(row, col + 6, "Cess", sub_header_style)

            ws1.write(row+1, col+1, "(a) Outward Taxable  supplies  (other than zero rated, nil rated and exempted)", line_content_style)
            ws1.write(row+2, col+1, "(b) Outward Taxable  supplies  (zero rated )", line_content_style)
            ws1.write(row+3, col+1, "(c) Other Outward Taxable  supplies (Nil rated, exempted)", line_content_style)
            ws1.write(row+4, col+1, "(d) Inward supplies (liable to reverse charge)", line_content_style)
            ws1.write(row+5, col+1, "(e) Non-GST Outward supplies", line_content_style)

            ws1.write(row+1, col+2, outward_taxable_supplies['taxable_value'], line_content_style)
            ws1.write(row+2, col+2, outward_taxable_zero_rated['taxable_value'], line_content_style)
            ws1.write(row+3, col+2, outward_taxable_exempted['taxable_value'], line_content_style)
            ws1.write(row+4, col+2, inward_reverse_charge['taxable_value'], line_content_style)
            ws1.write(row+5, col+2, outward_non_gst['taxable_value'], line_content_style)

            ws1.write(row+1, col+3, outward_taxable_supplies['igst'], line_content_style)
            ws1.write(row+2, col+3, outward_taxable_zero_rated['igst'], line_content_style)
            ws1.write(row+3, col+3, outward_taxable_exempted['igst'], line_content_style)
            ws1.write(row+4, col+3, inward_reverse_charge['igst'], line_content_style)
            ws1.write(row+5, col+3, outward_non_gst['igst'], line_content_style)

            ws1.write(row+1, col+4, outward_taxable_supplies['cgst'], line_content_style)
            ws1.write(row+2, col+4, outward_taxable_zero_rated['cgst'], line_content_style)
            ws1.write(row+3, col+4, outward_taxable_exempted['cgst'], line_content_style)
            ws1.write(row+4, col+4, inward_reverse_charge['cgst'], line_content_style)
            ws1.write(row+5, col+4, outward_non_gst['cgst'], line_content_style)

            ws1.write(row+1, col+5, outward_taxable_supplies['sgst'], line_content_style)
            ws1.write(row+2, col+5, outward_taxable_zero_rated['sgst'], line_content_style)
            ws1.write(row+3, col+5, outward_taxable_exempted['sgst'], line_content_style)
            ws1.write(row+4, col+5, inward_reverse_charge['sgst'], line_content_style)
            ws1.write(row+5, col+5, outward_non_gst['sgst'], line_content_style)

            ws1.write(row+1, col+6, outward_taxable_supplies['cess'], line_content_style)
            ws1.write(row+2, col+6, outward_taxable_zero_rated['cess'], line_content_style)
            ws1.write(row+3, col+6, outward_taxable_exempted['cess'], line_content_style)
            ws1.write(row+4, col+6, inward_reverse_charge['cess'], line_content_style)
            ws1.write(row+5, col+6, outward_non_gst['cess'], line_content_style)

            row += 8
            return row


        def prepare_eligible_itc(row):

            ws1.write_merge(row, row, col+1, col+5, "4. Eligible ITC", sub_header_style)
            row += 1
            ws1.write(row, col + 1, "Details", sub_header_style)
            ws1.write(row, col + 2, "Integrated Tax", sub_header_style)
            ws1.write(row, col + 3, "Central Tax", sub_header_style)
            ws1.write(row, col + 4, "State/UT Tax", sub_header_style)
            ws1.write(row, col + 5, "CESS", sub_header_style)

            ws1.write(row+1, col+1, "(A) ITC Available (Whether in full or part)", line_content_style)
            ws1.write(row+2, col+1, "   (1) Import of goods", line_content_style)
            ws1.write(row+3, col+1, "   (2) Import of services", line_content_style)
            ws1.write(row+4, col+1, "   (3) Inward supplies liable to reverse charge(other than 1 &2 above)", line_content_style)
            ws1.write(row+5, col+1, "   (4) Inward supplies from ISD", line_content_style)
            ws1.write(row+6, col+1, "   (5) All other ITC", line_content_style)
            ws1.write(row+7, col+1, "(B) ITC Reversed", line_content_style)
            ws1.write(row+8, col+1, "   (1) As per Rule 42 & 43 of SGST/CGST rules", line_content_style)
            ws1.write(row+9, col+1, "   (2) Others", line_content_style)
            ws1.write(row+10, col+1, "(C) Net ITC Available (A)-(B)", line_content_style)
            ws1.write(row+11, col+1, "(D) Ineligible ITC", line_content_style)
            ws1.write(row+12, col+1, "  (1) As per section 17(5) of CGST/SGST Act", line_content_style)
            ws1.write(row+13, col+1, "  (2) Others", line_content_style)

            ws1.write(row+2, col+2, import_goods['igst'], line_content_style)
            ws1.write(row+3, col+2, import_service['igst'], line_content_style)
            ws1.write(row+4, col+2, inward_reverse_charge['igst'], line_content_style)
            ws1.write(row+5, col+2, inward_isd['igst'], line_content_style)
            ws1.write(row+6, col+2, all_itc['igst'], line_content_style)
            ws1.write(row+8, col+2, itc_reversed_1['igst'], line_content_style)
            ws1.write(row+9, col+2, itc_reversed_2['igst'], line_content_style)
            ws1.write(row+11, col+2, ineligible_1['igst'], line_content_style)
            ws1.write(row+12, col+2, ineligible_2['igst'], line_content_style)

            ws1.write(row+2, col+3, import_goods['cgst'], line_content_style)
            ws1.write(row+3, col+3, import_service['cgst'], line_content_style)
            ws1.write(row+4, col+3, inward_reverse_charge['cgst'], line_content_style)
            ws1.write(row+5, col+3, inward_isd['cgst'], line_content_style)
            ws1.write(row+6, col+3, all_itc['cgst'], line_content_style)
            ws1.write(row+8, col+3, itc_reversed_1['cgst'], line_content_style)
            ws1.write(row+9, col+3, itc_reversed_2['cgst'], line_content_style)
            ws1.write(row+11, col+3, ineligible_1['cgst'], line_content_style)
            ws1.write(row+12, col+3, ineligible_2['cgst'], line_content_style)

            ws1.write(row+2, col+4, import_goods['sgst'], line_content_style)
            ws1.write(row+3, col+4, import_service['sgst'], line_content_style)
            ws1.write(row+4, col+4, inward_reverse_charge['sgst'], line_content_style)
            ws1.write(row+5, col+4, inward_isd['sgst'], line_content_style)
            ws1.write(row+6, col+4, all_itc['sgst'], line_content_style)
            ws1.write(row+8, col+4, itc_reversed_1['sgst'], line_content_style)
            ws1.write(row+9, col+4, itc_reversed_2['sgst'], line_content_style)
            ws1.write(row+11, col+4, ineligible_1['sgst'], line_content_style)
            ws1.write(row+12, col+4, ineligible_2['sgst'], line_content_style)

            ws1.write(row+2, col+5, import_goods['cess'], line_content_style)
            ws1.write(row+3, col+5, import_service['cess'], line_content_style)
            ws1.write(row+4, col+5, inward_reverse_charge['cess'], line_content_style)
            ws1.write(row+5, col+5, inward_isd['cess'], line_content_style)
            ws1.write(row+6, col+5, all_itc['cess'], line_content_style)
            ws1.write(row+8, col+5, itc_reversed_1['cess'], line_content_style)
            ws1.write(row+9, col+5, itc_reversed_2['cess'], line_content_style)
            ws1.write(row+11, col+5, ineligible_1['cess'], line_content_style)
            ws1.write(row+12, col+5, ineligible_2['cess'], line_content_style)

            row += 16
            return row

        def prepare_exempt_supplies(row):

            ws1.write_merge(row, row, col+1, col+3, "5. Values of exempt, Nil-rated and non-GST inward supplies", sub_header_style)
            row += 1
            ws1.write(row, col + 1, "Nature of supplies", sub_header_style)
            ws1.write(row, col + 2, "Inter-State Supplies", sub_header_style)
            ws1.write(row, col + 3, "Intra-State Supplies", sub_header_style)

            ws1.write(row+1, col+1, "From a supplier under composition scheme, Exempt  and Nil rated supply", line_content_style)
            ws1.write(row+2, col+1, "Non-GST Supply", line_content_style)

            ws1.write(row+1, col+2, inward_zero_gst['inter'], line_content_style)
            ws1.write(row+2, col+2, non_gst['inter'], line_content_style)

            ws1.write(row+1, col+3, inward_zero_gst['intra'], line_content_style)
            ws1.write(row+2, col+3, non_gst['intra'], line_content_style)

            row += 5
            return row

        def prepare_interest_late_fee(row):

            ws1.write_merge(row, row, col+1, col+5, "5.1 Interest & late fee payable", sub_header_style)
            row += 1
            ws1.write(row, col + 1, "Description", sub_header_style)
            ws1.write(row, col + 2, "Integrated Tax", sub_header_style)
            ws1.write(row, col + 3, "Central Tax", sub_header_style)
            ws1.write(row, col + 4, "State/UT Tax", sub_header_style)
            ws1.write(row, col + 5, "CESS", sub_header_style)

            ws1.write(row+1, col+1, 'Interest', line_content_style)
            ws1.write(row+1, col+2, interest['igst'], line_content_style)
            ws1.write(row+1, col+3, interest['cgst'], line_content_style)
            ws1.write(row+1, col+4, interest['sgst'], line_content_style)
            ws1.write(row+1, col+5, interest['cess'], line_content_style)

            row += 4
            return row

        def prepare_inter_state_unreg(row):

            ws1.write_merge(row, row, col+1, col+7, "3.2  Of the supplies shown in 3.1 (a), details of inter-state supplies made to unregistered persons, composition taxable person and UIN holders", sub_header_style)
            row += 1
            ws1.write_merge(row, row+1, col+1, col+1, "Place of Supply(State/UT)", sub_header_style)
            ws1.write_merge(row, row, col+2, col+3, "Supplies made to Unregistered Persons", sub_header_style)
            ws1.write_merge(row, row, col+4, col+5, "Supplies made to Composition Taxable Persons", sub_header_style)
            ws1.write_merge(row, row, col+6, col+7, "Supplies made to UIN holders", sub_header_style)
            ws1.write(row+1, col + 2, "Total Taxable value", sub_header_style)
            ws1.write(row+1, col + 3, "Amount of Integrated Tax", sub_header_style)
            ws1.write(row+1, col + 4, "Total Taxable value", sub_header_style)
            ws1.write(row+1, col + 5, "Amount of Integrated Tax", sub_header_style)
            ws1.write(row+1, col + 6, "Total Taxable value", sub_header_style)
            ws1.write(row+1, col + 7, "Amount of Integrated Tax", sub_header_style)
            ws1.write(row+2, col + 1, "1", sub_header_style)
            ws1.write(row+2, col + 2, "2", sub_header_style)
            ws1.write(row+2, col + 3, "3", sub_header_style)
            ws1.write(row+2, col + 4, "4", sub_header_style)
            ws1.write(row+2, col + 5, "5", sub_header_style)
            ws1.write(row+2, col + 6, "6", sub_header_style)
            ws1.write(row+2, col + 7, "7", sub_header_style)

            #pdb.set_trace()
            row += 2
            for place_of_supply_id, tx_line in pos_unreg_comp_uin_igst.items():
                place_of_supply = self.env['res.country.state'].browse(place_of_supply_id)
                row += 1
                ws1.write(row, col+1, place_of_supply.name, line_content_style)
                ws1.write(row, col+2, tx_line['unreg_taxable_amt'], line_content_style)
                ws1.write(row, col+3, tx_line['unreg_igst'], line_content_style)
                ws1.write(row, col+4, tx_line['comp_taxable_amt'], line_content_style)
                ws1.write(row, col+5, tx_line['comp_igst'], line_content_style)
                ws1.write(row, col+6, tx_line['uin_taxable_amt'], line_content_style)
                ws1.write(row, col+7, tx_line['uin_igst'], line_content_style)

            return row

        #Call the inner functions
        row = prepare_outward_supplies(row)
        row = prepare_eligible_itc(row)
        row = prepare_exempt_supplies(row)
        row = prepare_interest_late_fee(row)
        row = prepare_inter_state_unreg(row)

        return outward_taxable_supplies, outward_taxable_zero_rated, outward_taxable_exempted, outward_non_gst, \
               inward_reverse_charge, import_goods, import_service, inward_isd, all_itc, itc_reversed_1, \
               itc_reversed_2, ineligible_1, ineligible_2, inward_zero_gst, non_gst, interest, pos_unreg_comp_uin_igst



    """ Utility to get integer present in a string """
    def get_num(self, x):
        return int(''.join(ele for ele in x if ele.isdigit()) or 0)

    """ Utility to convert date/datetime to dd-mmm-yy format """
    def format_date(self, date_in):
        return datetime.strftime(date_in, "%d-%b-%y")
