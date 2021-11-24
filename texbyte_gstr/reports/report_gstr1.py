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
GST_POS = {'01': 'Jammu & Kashmir', '02': 'Himachal Pradesh', '03': 'Punjab', '04': 'Chandigarh', '05': 'Uttarakhand',\
        '06': 'Haryana', '07': 'Delhi', '08': 'Rajasthan', '09': 'Uttar Pradesh', '10': 'Bihar', '11': 'Sikkim',\
        '12': 'Arunachal Pradesh', '13': 'Nagaland', '14': 'Manipur', '15': 'Mizoram', '16': 'Tripura', '17': 'Meghalaya',\
        '18': 'Assam', '19': 'West Bengal', '20': 'Jharkhand', '21': 'Odisha', '22': 'Chhattisgarh', '23': 'Madhya Pradesh',\
        '24': 'Gujarat', '25': 'Daman & Diu', '26': 'Dadra & Nagar Haveli & Daman & Diu ', '27': 'Maharashtra', '29': 'Karnataka',\
        '30': 'Goa', '31': 'Lakshdweep', '32': 'Kerala', '33': 'Tamil Nadu', '34': 'Puducherry', '35': 'Andaman & Nicobar Islands',\
        '36': 'Telangana', '37': 'Andhra Pradesh', '38': 'Ladakh', '96': 'Foreign Country', '97': 'Other Territory'}

all_invoices = []
sorted_invoices = []
refund_invoices = []
canceled_invoices = []

#Map l10n_in_gst_treatment with GSTR1 excel template values
inv_tye_map = {
    'regular': 'Regular',
    'composition': 'Regular',
    'unregistered': 'Regular',
    'consumer': 'Regular',
    'overseas': 'Regular',       #TODO: export is regular?
    'special_economic_zone': 'SEZ supplies {} payment',    #With/Without payment, to be filled by checking tax amount
    'deemed_export': 'Deemed Exp'
    }

class GSTR1Report(models.TransientModel):

    _name = 'texbyte_gstr.report.gstr1'
    _description = 'GSTR1 report'

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


    def get_valid_invoices(self):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        # Searching for customer invoices
        from_date = self.date_from
        to_date = self.date_to
        refund_invoice_ids = []
        #if self.inv_type == 'cust_inv':
        inv_type_domain = ('move_type', 'in', ('out_invoice', 'out_refund'),)
        #else:
        #    inv_type_domain = ('move_type', 'in', ('in_invoice', 'in_refund'))

        #Get all invoices including canceled and refund
        all_invoices = self.env['account.move'].search([('invoice_date','>=', from_date),('invoice_date','<=', to_date),
                                inv_type_domain,('state', '!=', 'draft')])
        #Canceled invoices
        canceled_invoices = all_invoices.filtered(lambda i: i.state == 'cancel')
        #Refund invoices
        refund_invoices = all_invoices.filtered(lambda i: i.state != 'cancel' and i.move_type == 'out_refund')
        #Legitimate invoices -- other than canceled and refund
        invoices = all_invoices.filtered(lambda i: i.id not in canceled_invoices.ids + refund_invoices.ids )
        sorted_invoices = invoices.sorted(key=lambda p: (p.invoice_date, p.name))

    def generate_gstr1_report(self):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        #Error handling is not taken into consideraion
        self.ensure_one()
        fp = BytesIO()
        xl_workbook = xlwt.Workbook(encoding='utf-8')

        from_date = self.date_from
        to_date = self.date_to

        # Get the invoices
        self.get_valid_invoices()

        self.generate_b2b_report(xl_workbook)
        self.generate_b2ba_report(xl_workbook)
        self.generate_b2cl_report(xl_workbook)
        self.generate_b2cla_report(xl_workbook)
        self.generate_b2cs_report(xl_workbook)
        self.generate_b2csa_report(xl_workbook)
        self.generate_cdnr_report(xl_workbook)
        self.generate_cdnra_report(xl_workbook)
        self.generate_cdnur_report(xl_workbook)
        self.generate_cdnura_report(xl_workbook)
        self.generate_exp_report(xl_workbook)
        self.generate_expa_report(xl_workbook)
        self.generate_at_report(xl_workbook)
        self.generate_ata_report(xl_workbook)
        self.generate_atadj_report(xl_workbook)
        self.generate_atadja_report(xl_workbook)
        self.generate_exempted_report(xl_workbook)
        self.generate_hsn_report(xl_workbook)
        self.generate_docs_summary_report(xl_workbook)

        xl_workbook.save(fp)

        out = base64.encodebytes(fp.getvalue())
        self.write({'state': 'choose', 'report': out, 'filename':'gstr1_'+str(from_date)+'-'+str(to_date)+'.xls'})
        return {
            'name': 'GSTR1',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=texbyte_gstr.report.gstr1&id=" + str(self.id) + "&filename_field=filename&field=report&download=true&filename=" + self.filename,
            'target': 'current',
        }

    """ B2B (Business to Business report) """
    def generate_b2b_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        #Error handling is not taken into consideraion
        self.ensure_one()

        #TODO: format (group & split by tax rate):
        #   GSTIN           Inv No     Inv Date     Inv Value   PoS         Tax Rate    Taxable Value
        #   GSTIN000022     INV001     01/01/2018   5092.00     32-Kerala   5           2200
        #   GSTIN000022     INV001     01/01/2018   5092.00     32-Kerala   12          1600
        #Plan:
        #   1.  Get invoices within range. Filter out 'Canceled', 'Refund' & 'Refunded' invoices
        #   2.  Loop through invoices
        #   3.      Loop through invoice lines
        #   4.          Loop through invoice_line_tax__ids
        #   5.              Collect the invoice, untaxed_total and tax rate/name (such as 'GST @5%')
        #   6.  Loop through collected invoice and tax details
        #   7.      Print invoice details, tax rate/name and untaxed_total

        #wb1 = self.xl_workbook      # xlwt.Workbook(encoding='utf-8')
        ws1 = wb1.add_sheet('b2b')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "GSTIN/UIN of Recipient", sub_header_style)
        ws1.write(row, col + 2, "Receiver Name", sub_header_style)
        ws1.write(row, col + 3, "Invoice Number", sub_header_style)
        ws1.write(row, col + 4, "Invoice Date", sub_header_style)
        ws1.write(row, col + 5, "Invoice Value", sub_header_style)
        ws1.write(row, col + 6, "Place of Supply", sub_header_style)
        ws1.write(row, col + 7, "Reverse Charge", sub_header_style)
        ws1.write(row, col + 8, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 9, "Invoice Type", sub_header_style)
        ws1.write(row, col + 10, "E-Commerce GSTIN", sub_header_style)
        ws1.write(row, col + 11, "Rate", sub_header_style)
        ws1.write(row, col + 12, "Taxable Value", sub_header_style)
        ws1.write(row, col + 13, "Cess Amount", sub_header_style)

        row += 1
        #variables for columns and totals
        igst_amount = 0;
        cgst_amount = 0;
        sgst_amount = 0;

        invoice_gst_tax_lines = {}

        b2b_invoices = sorted_invoices.filtered(lambda p: p.partner_id.vat)  #GST registered customers
        #Summarize amount per tax rate for each invoice
        self.summarize_inv_per_tax_rate(b2b_invoices, invoice_gst_tax_lines)    #Fills invoice_gst_tax_lines, including lines with no tax_id
        invoice_gst_tax_lines.pop(0, False)                #Remove 0 tax entries, they are reported in Exempted

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            #Fill the invoice type

            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                place_of_supply = self.format_place_of_supply(invoice.partner_id.state_id or invoice.company_id.state_id)
                if float_is_zero(tax_rate, precision_digits=3):     #Skip zero rated/exempted rates
                    continue
                ws1.write(row, col + 1, invoice.partner_id.vat or "", line_content_style)
                ws1.write(row, col + 2, invoice.partner_id.name, line_content_style)
                ws1.write(row, col + 3, invoice.name, line_content_style)
                ws1.write(row, col + 4, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 5, invoice.amount_total, line_content_style)
                ws1.write(row, col + 6, place_of_supply, line_content_style)
                ws1.write(row, col + 7, invoice._is_reverse_charge_applicable() and "Y" or "N", line_content_style)
                ws1.write(row, col + 8, "", line_content_style)
                ws1.write(row, col + 9, self.gst_inv_type_from_l10n(invoice), line_content_style)  # "invoice.invoice_type" in branch, "branch revcharge_custom_ac" based on india_gst module.
                ws1.write(row, col + 10, "", line_content_style)  # TODO: E-Commerce GSTIN
                ws1.write(row, col + 11, tax_rate, line_content_style)
                ws1.write(row, col + 12, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 13, tax_amounts['cess_amount'], line_content_style)  # Cess amount

                row += 1

        #for invoice in canceled_refund_invoices:
        #    row += 1
        #    ws1.write(row, col + 1, invoice.name, line_content_style)
        #    ws1.write(row, col + 2, invoice.invoice_date, line_content_style)
        #    ws1.write(row, col + 3, invoice.state.title(), line_content_style)
        #    ws1.write(row, col + 4, invoice.origin, line_content_style)
        #    ws1.write(row, col + 5, invoice.partner_id.vat or "", line_content_style)
        #    partner_name = invoice.partner_id.vat and invoice.partner_id.name or invoice.partner_name
        #    ws1.write(row, col + 6, partner_name, line_content_style)
        return invoice_gst_tax_lines

    """ B2BA (Business to Business Amended report) """
    def generate_b2ba_report(self, wb1):
        #Error handling is not taken into consideraion
        self.ensure_one()

        ws1 = wb1.add_sheet('b2ba')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "GSTIN/UIN of Recipient", sub_header_style)
        ws1.write(row, col + 2, "Receiver Name", sub_header_style)
        ws1.write(row, col + 3, "Original Invoice Number", sub_header_style)
        ws1.write(row, col + 4, "Original Invoice Date", sub_header_style)
        ws1.write(row, col + 5, "Revised Invoice Number", sub_header_style)
        ws1.write(row, col + 6, "Revised Invoice Date", sub_header_style)
        ws1.write(row, col + 7, "Invoice Value", sub_header_style)
        ws1.write(row, col + 8, "Place of Supply", sub_header_style)
        ws1.write(row, col + 9, "Reverse Charge", sub_header_style)
        ws1.write(row, col + 10, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 11, "Invoice Type", sub_header_style)
        ws1.write(row, col + 12, "E-Commerce GSTIN", sub_header_style)
        ws1.write(row, col + 13, "Rate", sub_header_style)
        ws1.write(row, col + 14, "Taxable Value", sub_header_style)
        ws1.write(row, col + 15, "Cess Amount", sub_header_style)

        row += 1

    """ HSN Summary """
    def generate_hsn_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        #Error handling is not taken into consideraion
        self.ensure_one()

        ws1 = wb1.add_sheet('hsn')
        fp = BytesIO()

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 12 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "HSN", sub_header_style)
        ws1.write(row, col + 2, "Description", sub_header_style)
        ws1.write(row, col + 3, "UQC", sub_header_style)
        ws1.write(row, col + 4, "Total Quantity", sub_header_style)
        ws1.write(row, col + 5, "Total Value", sub_header_style)
        ws1.write(row, col + 6, "Rate", sub_header_style)
        ws1.write(row, col + 7, "Taxable Value", sub_header_style)
        ws1.write(row, col + 8, "Integrated Tax Amount", sub_header_style)
        ws1.write(row, col + 9, "Central Tax Amount", sub_header_style)
        ws1.write(row, col + 10, "State/UT Tax Amount", sub_header_style)
        ws1.write(row, col + 11, "Cess Amount", sub_header_style)

        hsn_summary_data = {}

        for invoice in sorted_invoices + refund_invoices:     #Subtract refunded quantity/amount
            sign = 1
            if invoice.move_type in ('out_refund', 'in_refund'):
                sign = -1

            foreign_curr = None
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                foreign_curr = invoice.currency_id
                curr_rate_date = invoice.date or invoice.invoice_date
                company_curr = invoice.company_id.currency_id
            for invoice_line in invoice.invoice_line_ids.filtered(lambda l: l.product_id):
                prod_id = invoice_line.product_id
                line_uom = invoice_line.product_uom_id
                line_qty = line_uom._compute_quantity(invoice_line.quantity, prod_id.uom_id)
                # Take care of currency conversion
                line_amount = foreign_curr._convert(invoice_line.price_subtotal, company_curr, invoice.company_id, curr_rate_date) \
                    if foreign_curr else invoice_line.price_subtotal
                line_total_amount = foreign_curr._convert(invoice_line.price_total, company_curr, invoice.company_id, curr_rate_date) \
                    if foreign_curr else invoice_line.price_total
                price = invoice_line.price_unit * (1 - (invoice_line.discount or 0.0) / 100.0)
                line_taxes = invoice_line.tax_ids.compute_all(price, invoice_line.move_id.currency_id, invoice_line.quantity, prod_id, invoice_line.move_id.partner_id)
                if foreign_curr:
                    line_taxes['total_excluded'] = foreign_curr._convert(line_taxes['total_excluded'], company_curr, invoice.company_id, curr_rate_date)
                    line_taxes['total_included'] = foreign_curr._convert(line_taxes['total_included'], company_curr, invoice.company_id, curr_rate_date)
                    for l in line_taxes['taxes']:
                        l['amount'] = foreign_curr._convert(l['amount'], company_curr, invoice.company_id, curr_rate_date)
                        l['base']   = foreign_curr._convert(l['base'], company_curr, invoice.company_id, curr_rate_date)

                #Add customer invoice, subtract credit note
                line_qty                     *= sign
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
                if hsn_summary_data.get(prod_id):
                    hsn_summary_data[prod_id][0] += line_qty
                    hsn_summary_data[prod_id][1] += line_total_amount
                    hsn_summary_data[prod_id][2] += line_amount
                    hsn_summary_data[prod_id][3] += igst_amount
                    hsn_summary_data[prod_id][4] += cgst_amount
                    hsn_summary_data[prod_id][5] += sgst_amount
                    hsn_summary_data[prod_id][6] += cess_amount
                else:
                    hsn_summary_data[prod_id] = [line_qty, line_total_amount, line_amount, igst_amount, cgst_amount, sgst_amount, cess_amount]

        #_logger.info(hsn_summary_data)

        #Can't sort dictionary, but get ordered list of tuples
        for product_hsn, hsn_sum in sorted(hsn_summary_data.items(), key=lambda p:p[0].name):
            if product_hsn.default_code in ('ADVANCE','CHARGES','DISCOUNT'):    #Skip Roundoff/Discount/Extra Charges/Advance items
                continue
            row += 1
            ws1.write(row, col + 1, product_hsn.l10n_in_hsn_code, line_content_style)
            ws1.write(row, col + 2, product_hsn.name, line_content_style)
            ws1.write(row, col + 3, product_hsn.uom_id.l10n_in_code, line_content_style)
            #Quantity in Base UoM
            ws1.write(row, col + 4, hsn_sum[0], line_content_style)
            #Amount
            ws1.write(row, col + 5, hsn_sum[1], line_content_style)
            ws1.write(row, col + 6, float(self.get_num(product_hsn.taxes_id.name.split('%')[0])))
            ws1.write(row, col + 7, hsn_sum[2], line_content_style)
            ws1.write(row, col + 8, hsn_sum[3], line_content_style)
            ws1.write(row, col + 9, hsn_sum[4], line_content_style)
            ws1.write(row, col + 10, hsn_sum[5], line_content_style)
            ws1.write(row, col + 11, hsn_sum[6], line_content_style)
        return hsn_summary_data

    """ B2CL (Business to Customer Large [>2.5L single invoice] report) """
    def generate_b2cl_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        #Error handling is not taken into consideraion
        self.ensure_one()

        #TODO: format (group & split by tax rate):
        #   GSTIN           Inv No     Inv Date     Inv Value   PoS         Tax Rate    Taxable Value
        #   GSTIN000022     INV001     01/01/2018   5092.00     32-Kerala   5           2200
        #   GSTIN000022     INV001     01/01/2018   5092.00     32-Kerala   12          1600
        #Plan:
        #   1.  Get invoices within range. Filter out 'Canceled', 'Refund' & 'Refunded' invoices
        #   2.  Loop through invoices
        #   3.      Loop through invoice lines
        #   4.          Loop through invoice_line_tax__ids
        #   5.              Collect the invoice, untaxed_total and tax rate/name (such as 'GST @5%')
        #   6.  Loop through collected invoice and tax details
        #   7.      Print invoice details, tax rate/name and untaxed_total

        #wb1 = self.xl_workbook      # xlwt.Workbook(encoding='utf-8')
        ws1 = wb1.add_sheet('b2cl')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Invoice Number", sub_header_style)
        ws1.write(row, col + 2, "Invoice Date", sub_header_style)
        ws1.write(row, col + 3, "Invoice Value", sub_header_style)
        ws1.write(row, col + 4, "Place of Supply", sub_header_style)
        ws1.write(row, col + 5, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 6, "Rate", sub_header_style)
        ws1.write(row, col + 7, "Taxable Value", sub_header_style)
        ws1.write(row, col + 8, "Cess Amount", sub_header_style)
        ws1.write(row, col + 9, "E-Commerce GSTIN", sub_header_style)

        row += 1
        #variables for columns and totals

        invoice_gst_tax_lines = {}

        b2cl_invoices = sorted_invoices.filtered(lambda p: not p.partner_id.vat \
                                                               and (p.company_id.state_id != p.partner_id.state_id if p.partner_id.state_id else True) \
                                                               and p.amount_untaxed_signed > B2CL_INVOICE_AMT_LIMIT)  #Unregistered inter-state large sale
        #Summarize amount per tax rate for each invoice
        self.summarize_inv_per_tax_rate(b2cl_invoices, invoice_gst_tax_lines)    #Fills invoice_gst_tax_lines
        invoice_gst_tax_lines.pop(0, False)		#Remove 0 tax entries, they are reported in Exempted

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                place_of_supply = self.format_place_of_supply(invoice.partner_id.state_id or invoice.company_id.state_id)
                if float_is_zero(tax_rate, precision_digits=3):     #Skip zero rated/exempted rates
                    continue
                ws1.write(row, col + 1, invoice.name, line_content_style)
                ws1.write(row, col + 2, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 3, invoice.amount_total, line_content_style)
                ws1.write(row, col + 4, place_of_supply, line_content_style)
                ws1.write(row, col + 5, "", line_content_style)
                ws1.write(row, col + 6, tax_rate, line_content_style)
                ws1.write(row, col + 7, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 8, tax_amounts['cess_amount'], line_content_style)  # Cess amount
                ws1.write(row, col + 9, "", line_content_style)  # TODO: E-Commerce GSTIN

                row += 1
        return invoice_gst_tax_lines

    """ B2CLA (Business to Customer Large Amended [>2.5L single invoice] report) """
    def generate_b2cla_report(self, wb1):
        #Error handling is not taken into consideraion
        self.ensure_one()

        ws1 = wb1.add_sheet('b2cla')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Original Invoice Number", sub_header_style)
        ws1.write(row, col + 2, "Original Invoice Date", sub_header_style)
        ws1.write(row, col + 3, "Original Place of Supply", sub_header_style)
        ws1.write(row, col + 4, "Revised Invoice Number", sub_header_style)
        ws1.write(row, col + 5, "Revised Invoice Date", sub_header_style)
        ws1.write(row, col + 6, "Invoice Value", sub_header_style)
        ws1.write(row, col + 7, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 8, "Rate", sub_header_style)
        ws1.write(row, col + 9, "Taxable Value", sub_header_style)
        ws1.write(row, col + 10, "Cess Amount", sub_header_style)
        ws1.write(row, col + 11, "E-Commerce GSTIN", sub_header_style)

        row += 1

    """ B2CS (Business to Customer Small) report """
    def generate_b2cs_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('b2cs')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Type", sub_header_style)
        ws1.write(row, col + 2, "Place of Supply", sub_header_style)
        ws1.write(row, col + 3, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 4, "Rate", sub_header_style)
        ws1.write(row, col + 5, "Taxable Value", sub_header_style)
        ws1.write(row, col + 6, "Cess Amount", sub_header_style)
        ws1.write(row, col + 7, "E-Commerce GSTIN", sub_header_style)

        row += 1

        invoice_pos_tax_lines = {}

        #Sale to unregistered customers other than B2CL (unreg. intra-state for any amount + unreg. inter-state <= 2.5 lakh)
        for invoice in sorted_invoices.filtered(lambda p: not p.partner_id.vat \
                                                                and not ((p.company_id.state_id != p.partner_id.state_id if p.partner_id.state_id else True) \
                                                                and p.amount_untaxed_signed > B2CL_INVOICE_AMT_LIMIT)):  #Unregistered customer sale other than B2CL
            #Can't use invoice.tax_line_ids directly because it will contain on individual/leaf taxes (like CGST@2.5%, SGST@2.5%)
            #while GSTR1 report needs the 'group' tax (like GST@5%).
            #Iterate through invoice.invoice_line_ids.invoice_line_tax_line_ids and collect/compute from there
            #Consider only sales within the country (skip export invoices) in B2CS
            if invoice.partner_id.country_id and invoice.partner_id.country_id != invoice.company_id.country_id:
                continue
            PoS = invoice.partner_id.state_id.id or invoice.company_id.state_id.id
            #pdb.set_trace()
            for invoice_line in invoice.invoice_line_ids:
                #TODO: handle CESS also here
                line_taxes = invoice_line.tax_ids.compute_all(invoice_line.price_unit, invoice.currency_id, invoice_line.quantity, invoice_line.product_id, invoice.partner_id)
                #_logger.info(line_taxes)
                gst_tax_id = None
                for ln_tx in invoice_line.tax_ids: #.sorted(reverse=True):
                    if 'GST' in ln_tx.name:    # GST taxes are named 'IGST', 'SGST', 'CGST' etc
                        gst_tax_id = ln_tx.id
                        if invoice_pos_tax_lines.get(PoS):
                            if invoice_pos_tax_lines[PoS].get(gst_tax_id):
                                invoice_pos_tax_lines[PoS][gst_tax_id]['base_amount'] += line_taxes['total_excluded']
                            else:
                                invoice_pos_tax_lines[PoS][gst_tax_id] = {'name': ln_tx.name, 'base_amount': line_taxes['total_excluded'], 'cess_amount': 0}
                            # Add Cess amount if the Cess tax is also included in this group tax
                        else:
                            invoice_pos_tax_lines[PoS] = {}
                            invoice_pos_tax_lines[PoS][gst_tax_id] = {'name': ln_tx.name, 'base_amount': line_taxes['total_excluded'], 'cess_amount': 0}
                        invoice_pos_tax_lines[PoS][gst_tax_id]['cess_amount'] += sum(l['amount'] for l in line_taxes['taxes'] if 'GST' not in l['name'])
                    elif gst_tax_id:       #CESS and other non-GST taxes
                        #TODO:Make the bold assumption that CESS is applied *after* GST taxes, so grouped_tax_lines[gst_tx_id] is already present
                        #if len(grouped_tax_lines.get(ln_tx)) > 1:
                        #Calculate CESS amount only
                        invoice_pos_tax_lines[PoS][gst_tax_id]['cess_amount'] += sum(l['amount'] for l in line_taxes['taxes'] if l['id'] == ln_tx.id)

		#TODO: report lines with no taxes (as 0 rate)?


        for place_of_supply_id, inv_tax_lines in invoice_pos_tax_lines.items():
            place_of_supply = self.format_place_of_supply(self.env['res.country.state'].browse(place_of_supply_id))
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                #tax_rate = float( tax_amounts['name'].split(' ')[1].split('%')[0] )
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                if float_is_zero(tax_rate, precision_digits=3):     #Skip zero rated/exempted rates
                    continue
                ws1.write(row, col + 1, "OE", line_content_style)       #TODO: 'OE'
                ws1.write(row, col + 2, place_of_supply, line_content_style)
                ws1.write(row, col + 3, "", line_content_style)
                ws1.write(row, col + 4, tax_rate, line_content_style)
                ws1.write(row, col + 5, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 6, tax_amounts['cess_amount'], line_content_style)  # Cess amount
                ws1.write(row, col + 7, "", line_content_style)  # TODO: E-Commerce GSTIN

                row += 1
        return invoice_pos_tax_lines

    """ B2CSA (Business to Customer Small Amended) report """
    def generate_b2csa_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('b2csa')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Financial Year", sub_header_style)
        ws1.write(row, col + 2, "Original Month", sub_header_style)
        ws1.write(row, col + 3, "Place of Supply", sub_header_style)
        ws1.write(row, col + 4, "Type", sub_header_style)
        ws1.write(row, col + 5, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 6, "Rate", sub_header_style)
        ws1.write(row, col + 7, "Taxable Value", sub_header_style)
        ws1.write(row, col + 8, "Cess Amount", sub_header_style)
        ws1.write(row, col + 9, "E-Commerce GSTIN", sub_header_style)

        row += 1

    """ Exempted (Nil Rated, Exempted and Non GST supplies) report """
    def generate_exempted_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('exemp')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Description", sub_header_style)
        ws1.write(row, col + 2, "Nil Rated Supplies", sub_header_style)
        ws1.write(row, col + 3, "Exempted (other than nil rated/non GST supply)", sub_header_style)
        ws1.write(row, col + 4, "Non-GST Supplies", sub_header_style)

        row += 1

        nil_rated_idx = 0
        exempted_idx  = 1
        non_gst_idx   = 2
        gst_exempted_values = { 'reg':{'inter-state':[0.0, 0.0, 0.0], 'intra-state':[0.0, 0.0, 0.0]}, 'unreg':{'inter-state':[0.0, 0.0, 0.0], 'intra-state':[0.0, 0.0, 0.0]} }
        for invoice in sorted_invoices:
            for invoice_line in invoice.invoice_line_ids.filtered(lambda l: l.product_id.default_code not in ('ADVANCE','CHARGES','DISCOUNT')):
                taxes = invoice_line.tax_ids.compute_all(invoice_line.price_unit, invoice.currency_id, invoice_line.quantity, invoice_line.product_id, invoice.partner_id)
                if float_compare(taxes['total_included'], taxes['total_excluded'], precision_digits=3) == 0:
                    #TODO: separate Nil-Rated, Exempted & Non-GST ones
                    #TODO: Assume there will be only 1 tax in the case of Zero tax
                    if taxes['taxes'] and 'GST' in taxes['taxes'][0]['name']:     #TODO: handle non-GST
                        l_index = nil_rated_idx
                    else:
                        l_index = exempted_idx

                    if invoice.partner_id.vat:
                        if not invoice.partner_id.state_id or invoice.partner_id.state_id == invoice.company_id.state_id:
                            gst_exempted_values['reg']['intra-state'][l_index] += invoice_line.price_subtotal
                        else:
                            gst_exempted_values['reg']['inter-state'][l_index] += invoice_line.price_subtotal
                    else:
                        if not invoice.partner_id.state_id or invoice.partner_id.state_id == invoice.company_id.state_id:
                            gst_exempted_values['unreg']['intra-state'][l_index] += invoice_line.price_subtotal
                        else:
                            gst_exempted_values['unreg']['inter-state'][l_index] += invoice_line.price_subtotal

        for exemp_key, exemp_val in gst_exempted_values.items():
            if exemp_key == 'reg':
                ws1.write(row, col+1, 'Inter-State supplies to registered persons')
                ws1.write(row, col+2, exemp_val['inter-state'][0])
                ws1.write(row, col+3, exemp_val['inter-state'][1])
                ws1.write(row, col+4, exemp_val['inter-state'][2])
                row += 1
                ws1.write(row, col+1, 'Intra-State supplies to registered persons')
                ws1.write(row, col+2, exemp_val['intra-state'][0])
                ws1.write(row, col+3, exemp_val['intra-state'][1])
                ws1.write(row, col+4, exemp_val['intra-state'][2])
            else:
                ws1.write(row, col+1, 'Inter-State supplies to unregistered persons')
                ws1.write(row, col+2, exemp_val['inter-state'][0])
                ws1.write(row, col+3, exemp_val['inter-state'][1])
                ws1.write(row, col+4, exemp_val['inter-state'][2])
                row += 1
                ws1.write(row, col+1, 'Intra-State supplies to unregistered persons')
                ws1.write(row, col+2, exemp_val['intra-state'][0])
                ws1.write(row, col+3, exemp_val['intra-state'][1])
                ws1.write(row, col+4, exemp_val['intra-state'][2])

            row += 1

    """ CDNR (Credit/Debit Note Registered) """
    def generate_cdnr_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('cdnr')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "GSTIN/UIN of Recipient", sub_header_style)
        ws1.write(row, col + 2, "Receiver Name", sub_header_style)
        ws1.write(row, col + 3, "Note Number", sub_header_style)
        ws1.write(row, col + 4, "Note Date", sub_header_style)
        ws1.write(row, col + 5, "Note Type", sub_header_style)
        ws1.write(row, col + 6, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 7, "Reverse Charge", sub_header_style)
        ws1.write(row, col + 8, "Note Supply Type", sub_header_style)
        ws1.write(row, col + 9, "Note Value", sub_header_style)
        ws1.write(row, col + 10, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 11, "Rate", sub_header_style)
        ws1.write(row, col + 12, "Taxable Value", sub_header_style)
        ws1.write(row, col + 13, "Cess Amount", sub_header_style)

        row += 1

        invoice_gst_tax_lines = {}

        cdnr_invoices = refund_invoices.filtered(lambda p: p.partner_id.vat and \
                                                        p.move_type in ('in_refund','out_refund')) #GST registered customers
        #Summarize amount per tax rate for each invoice
        self.summarize_inv_per_tax_rate(cdnr_invoices, invoice_gst_tax_lines)    #Fills invoice_gst_tax_lines

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                place_of_supply = self.format_place_of_supply(invoice.partner_id.state_id or invoice.company_id.state_id)
                ws1.write(row, col + 1, invoice.partner_id.vat, line_content_style)
                ws1.write(row, col + 2, invoice.partner_id.name, line_content_style)
                ws1.write(row, col + 3, invoice.name, line_content_style)
                ws1.write(row, col + 4, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 5, invoice.move_type == 'in_refund' and "D" or "C", line_content_style)
                ws1.write(row, col + 6, place_of_supply, line_content_style)
                ws1.write(row, col + 7, "Y" if invoice._is_reverse_charge_applicable() else "N", line_content_style)
                ws1.write(row, col + 8, self.gst_inv_type_from_l10n(invoice), line_content_style)
                ws1.write(row, col + 9, invoice.amount_total, line_content_style)
                ws1.write(row, col + 10, "", line_content_style)
                ws1.write(row, col + 11, tax_rate, line_content_style)
                ws1.write(row, col + 12, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 13, tax_amounts['cess_amount'], line_content_style)

                row += 1
        return invoice_gst_tax_lines

    """ CDNRA (Amended Credit/Debit Note) """
    def generate_cdnra_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('cdnra')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "GSTIN/UIN of Recipient", sub_header_style)
        ws1.write(row, col + 2, "Receiver Name", sub_header_style)
        ws1.write(row, col + 3, "Original Note Number", sub_header_style)
        ws1.write(row, col + 4, "Original Note Date", sub_header_style)
        ws1.write(row, col + 5, "Revised Note Number", sub_header_style)
        ws1.write(row, col + 6, "Revised Note Date", sub_header_style)
        ws1.write(row, col + 7, "Note Type", sub_header_style)
        ws1.write(row, col + 8, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 9, "Reverse Charge", sub_header_style)
        ws1.write(row, col + 10, "Note Supply Type", sub_header_style)
        ws1.write(row, col + 11, "Note Value", sub_header_style)
        ws1.write(row, col + 12, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 13, "Rate", sub_header_style)
        ws1.write(row, col + 14, "Taxable Value", sub_header_style)
        ws1.write(row, col + 15, "Cess Amount", sub_header_style)

        row += 1

    """ CDNUR (Credit/Debit Note Unregistered, more than 2.5 lakh) """
    def generate_cdnur_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('cdnur')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "UR Type", sub_header_style)
        ws1.write(row, col + 2, "Note Number", sub_header_style)
        ws1.write(row, col + 3, "Note date", sub_header_style)
        ws1.write(row, col + 4, "Note Type", sub_header_style)
        ws1.write(row, col + 5, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 6, "Note Value", sub_header_style)
        ws1.write(row, col + 7, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 8, "Rate", sub_header_style)
        ws1.write(row, col + 9, "Taxable Value", sub_header_style)
        ws1.write(row, col + 10, "Cess Amount", sub_header_style)

        row += 1

        invoice_gst_tax_lines = {}

        cdnur_invoices = refund_invoices.filtered(lambda p: not p.partner_id.vat and (p.company_id.state_id != p.partner_id.state_id if p.partner_id.state_id else True) \
                                                     and (p.amount_untaxed_signed * -1) > B2CL_INVOICE_AMT_LIMIT and p.move_type in ('in_refund', 'out_refund'))
        #Summarize amount per tax rate for each invoice
        self.summarize_inv_per_tax_rate(cdnur_invoices, invoice_gst_tax_lines)    #Fills invoice_gst_tax_lines

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                place_of_supply = self.format_place_of_supply(invoice.partner_id.state_id or invoice.company_id.state_id)
                ws1.write(row, col + 1, 'B2CL', line_content_style)
                ws1.write(row, col + 2, invoice.name, line_content_style)
                ws1.write(row, col + 3, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 4, invoice.move_type == 'in_refund' and "D" or "C", line_content_style)
                ws1.write(row, col + 5, place_of_supply, line_content_style)
                ws1.write(row, col + 6, invoice.amount_total, line_content_style)
                ws1.write(row, col + 7, "", line_content_style)
                ws1.write(row, col + 8, tax_rate, line_content_style)
                ws1.write(row, col + 9, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 10, tax_amounts['cess_amount'], line_content_style)

                row += 1
        return invoice_gst_tax_lines

    """ CDNURA (Amended Credit/Debit Note Unregistered, more than 2.5 lakh) """
    def generate_cdnura_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('cdnura')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "UR Type", sub_header_style)
        ws1.write(row, col + 2, "Original Note Number", sub_header_style)
        ws1.write(row, col + 3, "Original Note Date", sub_header_style)
        ws1.write(row, col + 4, "Revised Note Number", sub_header_style)
        ws1.write(row, col + 5, "Revised Note Date", sub_header_style)
        ws1.write(row, col + 6, "Note Type", sub_header_style)
        ws1.write(row, col + 7, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 8, "Note Value", sub_header_style)
        ws1.write(row, col + 9, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 10, "Rate", sub_header_style)
        ws1.write(row, col + 11, "Taxable Value", sub_header_style)
        ws1.write(row, col + 12, "Cess Amount", sub_header_style)

        row += 1

    """ EXP (Exports supplies including supplies to SEZ/SEZ Developer or deemed exports) """
    def generate_exp_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('exp')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Export Type", sub_header_style)
        ws1.write(row, col + 2, "Invoice Number", sub_header_style)
        ws1.write(row, col + 3, "Invoice date", sub_header_style)
        ws1.write(row, col + 4, "Invoice Value", sub_header_style)
        ws1.write(row, col + 5, "Port Code", sub_header_style)
        ws1.write(row, col + 6, "Shipping Bill Number", sub_header_style)
        ws1.write(row, col + 7, "Shipping Bill Date", sub_header_style)
        ws1.write(row, col + 8, "Rate", sub_header_style)
        ws1.write(row, col + 9, "Taxable Value", sub_header_style)
        ws1.write(row, col + 10, "Cess Amount", sub_header_style)

        row += 1

        invoice_gst_tax_lines = {}

        exp_invoices = sorted_invoices.filtered(lambda p: p.l10n_in_gst_treatment == 'overseas')  #Export invoices (excluding reversal documents)
        #Summarize amount per tax rate for each invoice
        self.summarize_inv_per_tax_rate(exp_invoices, invoice_gst_tax_lines)    #Fills invoice_gst_tax_lines, including lines with no tax_id

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            foreign_curr = None  # consider currency when filling total invoice value
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                foreign_curr = invoice.currency_id
                curr_rate_date = invoice.date or invoice.date_invoice
                company_curr = invoice.company_id.currency_id
            total_amount = foreign_curr._convert(invoice.amount_total, company_curr, invoice.company_id, curr_rate_date) if foreign_curr else invoice.amount_total
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                ws1.write(row, col + 1, "WOPAY" if float_is_zero(tax_rate, precision_digits=3) else "WPAY", line_content_style)  #With/without payment of tax
                ws1.write(row, col + 2, invoice.name, line_content_style)
                ws1.write(row, col + 3, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 4, total_amount, line_content_style)
                ws1.write(row, col + 5, invoice.l10n_in_shipping_port_code_id.code, line_content_style)
                ws1.write(row, col + 6, invoice.l10n_in_shipping_bill_number, line_content_style)
                ws1.write(row, col + 7, self.format_date(invoice.l10n_in_shipping_bill_date) if invoice.l10n_in_shipping_bill_date else "", line_content_style)
                ws1.write(row, col + 8, tax_rate, line_content_style)
                ws1.write(row, col + 9, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 10, tax_amounts['cess_amount'], line_content_style)    #Cess amount

                row += 1
        return invoice_gst_tax_lines

    """ EXPA (Amended Export) report """
    def generate_expa_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('expa')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Export Type", sub_header_style)
        ws1.write(row, col + 2, "Original Invoice Number", sub_header_style)
        ws1.write(row, col + 3, "Original Invoice date", sub_header_style)
        ws1.write(row, col + 4, "Revised Invoice Number", sub_header_style)
        ws1.write(row, col + 5, "Revised Invoice date", sub_header_style)
        ws1.write(row, col + 6, "Invoice Value", sub_header_style)
        ws1.write(row, col + 7, "Port Code", sub_header_style)
        ws1.write(row, col + 8, "Shipping Bill Number", sub_header_style)
        ws1.write(row, col + 9, "Shipping Bill Date", sub_header_style)
        ws1.write(row, col + 10, "Rate", sub_header_style)
        ws1.write(row, col + 11, "Taxable Value", sub_header_style)
        ws1.write(row, col + 12, "Cess Amount", sub_header_style)

        row += 1



    """ AT (Tax on Advance) report """
    def generate_at_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('at')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 2, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 3, "Rate", sub_header_style)
        ws1.write(row, col + 4, "Gross Advance Received", sub_header_style)
        ws1.write(row, col + 5, "Cess Amount", sub_header_style)

        row += 1

    """ ATA (Amended Tax on Advance) report """
    def generate_ata_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('ata')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Financial Year", sub_header_style)
        ws1.write(row, col + 2, "Original Month", sub_header_style)
        ws1.write(row, col + 3, "Original Place of Supply", sub_header_style)
        ws1.write(row, col + 4, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 5, "Rate", sub_header_style)
        ws1.write(row, col + 6, "Gross Advance Received", sub_header_style)
        ws1.write(row, col + 7, "Cess Amount", sub_header_style)

        row += 1

    """ ATADJ (Advance adjustments) report """
    def generate_atadj_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('atadj')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 2, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 3, "Rate", sub_header_style)
        ws1.write(row, col + 4, "Gross Advance Adjusted", sub_header_style)
        ws1.write(row, col + 5, "Cess Amount", sub_header_style)

        row += 1

    """ ATA (Amended Tax on Advance) report """
    def generate_atadja_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('atadja')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Financial Year", sub_header_style)
        ws1.write(row, col + 2, "Original Month", sub_header_style)
        ws1.write(row, col + 3, "Original Place of Supply", sub_header_style)
        ws1.write(row, col + 4, "Applicable % of Tax Rate", sub_header_style)
        ws1.write(row, col + 5, "Rate", sub_header_style)
        ws1.write(row, col + 6, "Gross Advance Adjusted", sub_header_style)
        ws1.write(row, col + 7, "Cess Amount", sub_header_style)

        row += 1

    """ Docs (Summary of Documents) """
    def generate_docs_summary_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('docs')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 0
        col = -1
        ws1.row(row).height = 500
        ws1.write(row, col + 1, "Nature of Document", sub_header_style)
        ws1.write(row, col + 2, "Sr. No. From", sub_header_style)
        ws1.write(row, col + 3, "Sr. No. To", sub_header_style)
        ws1.write(row, col + 4, "Total Number", sub_header_style)
        ws1.write(row, col + 5, "Cancelled", sub_header_style)

        row += 1
        #Outgoing invoices + Debit Notes (incoming refund)
        sorted_invs = all_invoices + self.env['account.move'].search([('invoice_date','>=', self.date_from),
                                    ('invoice_date','<=', self.date_to),('move_type', '=', 'in_refund'),('state', '!=', 'draft')])
        if not sorted_invs:
            return
        #Group by journal (for different number sequence) and by move_type (for invoice/debit note) and sort by invoice number
        sorted_invs = sorted_invs.sorted(key=lambda p: (p.journal_id.id, p.move_type, p.name)) #per journal, move_type, sort invoice numbers
        #_logger.info(sorted_invs.mapped(lambda p: (p.journal_id.id, p.move_type, p.name)))

        journals = set(sorted_invs.mapped('journal_id'))
        inv_types = set(sorted_invs.mapped('move_type'))
        inv_types.discard('out_refund')   #Credit Notes are not required to report
        for j in journals:
            for t in inv_types:
                #Slice invoices and cancelled invoices for this journal and this move_type alone
                this_jnl_type_invs = sorted_invs.filtered(lambda p: p.journal_id == j and p.move_type == t)
                this_jnl_type_canceled = this_jnl_type_invs.filtered(lambda p: p.state == 'cancel')
                if not this_jnl_type_invs:
                    continue
                ws1.write(row, col + 1, "Invoices for outward supply" if t == 'out_invoice' else "Debit Note")
                ws1.write(row, col + 2, this_jnl_type_invs[0].name)
                ws1.write(row, col + 3, this_jnl_type_invs[-1].name)
                ws1.write(row, col + 4, len(this_jnl_type_invs))
                ws1.write(row, col + 5, len(this_jnl_type_canceled))
                row += 1

    """ Utility method to summarize tax amount by rate, per invoice """
    def summarize_inv_per_tax_rate(self, invoice_list, invoice_gst_tax_lines):
        #@invoice_list: list of invoices
        #@invoice_gst_tax_lines: returned summary by tax: {'invoice': {'gst_tax': {'name','base_amount','cess_amount'}, ...}, ...}
        invoice_gst_tax_lines.clear()
        for invoice in invoice_list:
            #Can't use invoice.tax_line_ids directly because it will contain on individual/leaf taxes (like CGST@2.5%, SGST@2.5%)
            #while GSTR1 report needs the 'group' tax (like GST@5%).
            #Iterate through invoice.invoice_line_ids.invoice_line_tax_line_ids and collect/compute from there
            #for tax_line in invoice.tax_line_ids:
            grouped_tax_lines = {}

            foreign_curr = None
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                foreign_curr = invoice.currency_id
                curr_rate_date = invoice.date or invoice.invoice_date
                company_curr = invoice.company_id.currency_id

            for inv_line in invoice.invoice_line_ids:
                price = inv_line.price_unit * (1 - (inv_line.discount or 0.0) / 100.0)
                # Take care of currency conversion
                line_amount = foreign_curr._convert(inv_line.price_subtotal, company_curr, invoice.company_id, curr_rate_date) \
                    if foreign_curr else inv_line.price_subtotal

                line_taxes = inv_line.tax_ids.compute_all(price, invoice.currency_id, inv_line.quantity, inv_line.product_id, invoice.partner_id)
                if foreign_curr:
                    line_taxes['total_excluded'] = foreign_curr._convert(line_taxes['total_excluded'], company_curr, invoice.company_id, curr_rate_date)
                    line_taxes['total_included'] = foreign_curr._convert(line_taxes['total_included'], company_curr, invoice.company_id, curr_rate_date)
                    for l in line_taxes['taxes']:
                        l['amount'] = foreign_curr._convert(l['amount'], company_curr, invoice.company_id, curr_rate_date)
                        l['base'] = foreign_curr._convert(l['base'], company_curr, invoice.company_id, curr_rate_date)

                #_logger.info(line_taxes)
                #_logger.info(inv_line.tax_ids.sorted(reverse=True))
                gst_tax_id = 0
                for ln_tx in inv_line.tax_ids: #.sorted(reverse=True):
                    if 'GST' in ln_tx.name:    # GST taxes are named 'IGST', 'SGST', 'CGST' etc
                        gst_tax_id = ln_tx.id
                        if grouped_tax_lines.get(gst_tax_id):
                            grouped_tax_lines[gst_tax_id]['base_amount'] += line_taxes['total_excluded']
                        else:
                            grouped_tax_lines[gst_tax_id] = {'name': ln_tx.name, 'base_amount': line_taxes['total_excluded'], 'cess_amount': 0}
                        # Add Cess amount if the Cess tax is also included in this group tax
                        grouped_tax_lines[gst_tax_id]['cess_amount'] += sum(l['amount'] for l in line_taxes['taxes'] if 'GST' not in l['name'])
                    elif gst_tax_id and not grouped_tax_lines[gst_tax_id]['cess_amount']:       #CESS and other non-GST taxes
                        #TODO:Make the bold assumption that CESS is applied *after* GST taxes, so grouped_tax_lines[gst_tx_id] is already present
                        #if len(grouped_tax_lines.get(ln_tx)) > 1:
                        #Calculate CESS amount only
                        grouped_tax_lines[gst_tax_id]['cess_amount'] += sum(l['amount'] for l in line_taxes['taxes'] if l['id'] == ln_tx.id)
                        #else:
                        #    grouped_tax_lines[ln_tx][1] = line_taxes['total_excluded']

                #No taxes at this line (TODO: identify & skip roundoff). These entries may need to be filtered out by callers
                if not gst_tax_id:
                    gst_tax_id = 0    #No tax, id set as 0
                    if grouped_tax_lines.get(gst_tax_id):
                        grouped_tax_lines[gst_tax_id]['base_amount'] += line_amount
                    else:
                        grouped_tax_lines[gst_tax_id] = {'name': '0%', 'base_amount': line_amount, 'cess_amount': 0}


            invoice_gst_tax_lines[invoice] = grouped_tax_lines


    """ Utility to get integer present in a string """
    def get_num(self, x):
        return int(''.join(ele for ele in x if ele.isdigit()) or 0)  #Doesn't handle real numbers

    """ Utility to convert date/datetime to dd-mmm-yy format """
    def format_date(self, date_in):
        return datetime.strftime(date_in, "%d-%b-%y")

    """ Utility to map l10n_in_gst_treatment to Invoice Type in GSTR excel format """
    def gst_inv_type_from_l10n(self, invoice):
        inv_type_gst = inv_tye_map[invoice.l10n_in_gst_treatment] if invoice.l10n_in_gst_treatment else "Regular"
        if inv_type_gst.startswith('SEZ'):
            with_or_without = "without" if invoice.amount_tax == 0.00 else "with"
            inv_type_gst = inv_type_gst.format(with_or_without)     #SEZ with/without payment
        return inv_type_gst

    """ Utility to get Place of Supply in GST format"""
    def format_place_of_supply(self, state_id):
        return state_id and (state_id.l10n_in_tin + "-" + GST_POS.get(state_id.l10n_in_tin)) or ""
