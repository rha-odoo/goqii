from odoo.tests import tagged
from .testcases import GSTRTestcases
from datetime import date
import xlwt

@tagged('post_install', '-at_install')
class CheckReport1(GSTRTestcases):
    def test_gstr1(self):
        today = date.today()
        gstr1 = self.env['texbyte_gstr.report.gstr1'].create({'date_from': today, 'date_to': today})
        xl_workbook = xlwt.Workbook(encoding='utf-8')
        print("----------GSTR1--------")
        gstr1.get_valid_invoices()
        b2b = gstr1.generate_b2b_report(xl_workbook)
        b2b_vals = self.compute_value(b2b)
        print("B2B TAXABLE, Expected: %d; Received: %d " % (17200, b2b_vals))
        self.assertEqual(b2b_vals, 17200.0)

        b2cl = gstr1.generate_b2cl_report(xl_workbook)
        b2cl_vals = self.compute_value(b2cl)
        print("B2CL TAXABLE, Expected: %d; Received: %d " % (300000, b2cl_vals))
        self.assertEqual(b2cl_vals, 300000.0)

        b2cs = gstr1.generate_b2cs_report(xl_workbook)
        b2cs_vals = self.compute_b2cs(b2cs)
        print("B2CS TAXABLE, Expected: %d; Received: %d " % (6000, b2cs_vals))
        self.assertEqual(b2cs_vals, 6000.0)

        cdnr = gstr1.generate_cdnr_report(xl_workbook)
        cdnr_vals = self.compute_value(cdnr)
        print("CDNR TAXABLE, Expected: %d; Received: %d " % (3000, cdnr_vals))
        self.assertEqual(cdnr_vals, 3000.0)

        cdnur = gstr1.generate_cdnur_report(xl_workbook)
        cdnur_vals = self.compute_value(cdnur)
        print("CDNUR TAXABLE, Expected: %d; Received: %d " % (300000, b2b_vals))
        self.assertEqual(cdnur_vals, 300000.0)

        hsn = gstr1.generate_hsn_report(xl_workbook)
        hsn_out_vals = self.compute_hsn(hsn)
        print("HSN OUT PRODUCT A TAXABLE:, Expected: %d; Received: %d " % (1000, hsn_out_vals['Product A'][2]))
        self.assertEqual(hsn_out_vals['Product A'][2], 1000.0)
        self.assertEqual(hsn_out_vals['Product A'][3], 0.0)
        self.assertEqual(hsn_out_vals['Product A'][4], 25.0)
        self.assertEqual(hsn_out_vals['Product A'][5], 25.0)
        print("HSN OUT PRODUCT B TAXABLE:, Expected: %d; Received: %d " % (19200, hsn_out_vals['Product B'][2]))
        self.assertEqual(hsn_out_vals['Product B'][2], 19200.0)
        self.assertEqual(hsn_out_vals['Product B'][3], 660.0)
        self.assertEqual(hsn_out_vals['Product B'][4], 0.0)
        self.assertEqual(hsn_out_vals['Product B'][5], 0.0)
        print("HSN OUT PRODUCT LARGE TAXABLE:, Expected: %d; Received: %d " % (0.0, hsn_out_vals['Product Large'][2]))
        self.assertEqual(hsn_out_vals['Product Large'][2], 0.0)
        self.assertEqual(hsn_out_vals['Product Large'][3], 0.0)
        self.assertEqual(hsn_out_vals['Product Large'][4], 0.0)
        self.assertEqual(hsn_out_vals['Product Large'][5], 0.0)
        print("HSN OUT SERVICE1 TAXABLE:, Expected: %d; Received: %d " % (2000, hsn_out_vals['Service 1'][2]))
        self.assertEqual(hsn_out_vals['Service 1'][2], 2000.0)
        self.assertEqual(hsn_out_vals['Service 1'][3], 0.0)
        self.assertEqual(hsn_out_vals['Service 1'][4], 50.0)
        self.assertEqual(hsn_out_vals['Service 1'][5], 50.0)
        print("HSN OUT SERVICE2 TAXABLE:, Expected: %d; Received: %d " % (2000, hsn_out_vals['Service 2'][2]))
        self.assertEqual(hsn_out_vals['Service 2'][2], 2000.0)
        self.assertEqual(hsn_out_vals['Service 2'][3], 100.0)
        self.assertEqual(hsn_out_vals['Service 2'][4], 0.0)
        self.assertEqual(hsn_out_vals['Service 2'][5], 0.0)

    def compute_value(self, invoice_gst_tax_lines):
        taxable = 0
        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)):
            for tax_id, tax_amounts in inv_tax_lines.items():
                taxable += tax_amounts['base_amount']
        return taxable

    def compute_b2cs(self, invoice_pos_tax_lines):
        taxable = 0
        for place_id, tax_lines in invoice_pos_tax_lines.items():
            for tax_id, tax_amount in tax_lines.items():
                taxable += tax_amount['base_amount']
        return taxable

    def compute_hsn(self, hsn_vals):
        hsn_vals_updated = {}
        for product_hsn, hsn_sum in sorted(hsn_vals.items(), key=lambda p: p[0].name):
            vals = []
            vals.append(hsn_sum[0])  # hsn quantity
            vals.append(hsn_sum[1])  # total value
            vals.append(hsn_sum[2])  # taxable value
            vals.append(hsn_sum[3])  # igst
            vals.append(hsn_sum[4])  # cgst
            vals.append(hsn_sum[5])  # sgst
            vals.append(hsn_sum[6])  # cess
            hsn_vals_updated[product_hsn.name] = vals
        return hsn_vals_updated
