from odoo.tests import tagged
from .testcases import GSTRTestcases
from datetime import date
import xlwt


@tagged('post_install', '-at_install')
class CheckReport9(GSTRTestcases):
    def test_gstr9(self):
        today = date.today()
        gstr9 = self.env['texbyte_gstr.report.gstr9'].create({'date_from': today, 'date_to': today})
        xl_workbook = xlwt.Workbook(encoding='utf-8')
        print("----------GSTR9--------")
        gstr9.get_valid_invoices()
        values_tax_payable = gstr9.outward_tax_payable_report(xl_workbook)
        values_tax_not_payable = gstr9.outward_tax_not_payable_report(xl_workbook)
        itc = gstr9.itc_availed(xl_workbook)
        hsn_out = gstr9.hsn_outward(xl_workbook)
        hsn_in = gstr9.hsn_inward(xl_workbook)


        #b2b
        print("B2B Taxable, Expected: %d; Received: %d " % (15200, values_tax_payable[0]['taxable_value']))
        self.assertEqual(values_tax_payable[0]['taxable_value'], 15200.0)
        self.assertEqual(values_tax_payable[0]['igst'], 760.0)
        self.assertEqual(values_tax_payable[0]['cgst'], 0.0)
        self.assertEqual(values_tax_payable[0]['sgst'], 0.0)

        #b2c
        print("B2C Taxable, Expected: %d; Received: %d " % (6000, values_tax_payable[1]['taxable_value']))
        self.assertEqual(values_tax_payable[1]['taxable_value'], 6000.0)
        self.assertEqual(values_tax_payable[1]['igst'], 150.0)
        self.assertEqual(values_tax_payable[1]['cgst'], 75.0)
        self.assertEqual(values_tax_payable[1]['sgst'], 75.0)

        #sez with payment
        print("SEZ WITH PAY Taxable, Expected: %d; Received: %d " % (3800, values_tax_payable[4]['taxable_value']))
        self.assertEqual(values_tax_payable[4]['taxable_value'], 3800.0)
        self.assertEqual(values_tax_payable[4]['igst'], 190)
        self.assertEqual(values_tax_payable[4]['cgst'], 0.0)
        self.assertEqual(values_tax_payable[4]['sgst'], 0.0)

        #deemed
        print("DEEMED Taxable, Expected: %d; Received: %d " % (8400, values_tax_payable[5]['taxable_value']))
        self.assertEqual(values_tax_payable[5]['taxable_value'], 8400.0)
        self.assertEqual(values_tax_payable[5]['igst'], 420.0)
        self.assertEqual(values_tax_payable[5]['cgst'], 0.0)
        self.assertEqual(values_tax_payable[5]['sgst'], 0.0)

        #credit note
        print("CREDIT Taxable, Expected: %d; Received: %d " % (3000, values_tax_payable[6]['taxable_value']))
        self.assertEqual(values_tax_payable[6]['taxable_value'], -3000.0)
        self.assertEqual(values_tax_payable[6]['igst'], -150)
        self.assertEqual(values_tax_payable[6]['cgst'], 0.0)
        self.assertEqual(values_tax_payable[6]['sgst'], 0.0)

        #debit note
        print("DEBIT Taxable, Expected: %d; Received: %d " % (500, values_tax_payable[7]['taxable_value']))
        self.assertEqual(values_tax_payable[7]['taxable_value'], -500.0)
        self.assertEqual(values_tax_payable[7]['igst'], 0.0)
        self.assertEqual(values_tax_payable[7]['cgst'], -12.5)
        self.assertEqual(values_tax_payable[7]['sgst'], -12.5)

        #supply_sez_wop
        print("SEZ WITHOUT PAY, Expected: %d; Received: %d " % (2000, values_tax_not_payable[1]['taxable_value']))
        self.assertEqual(values_tax_not_payable[1]['taxable_value'], 2000.0)

        #exempted
        print("EXEMPTED, Expected: %d; Received: %d " % (2000, values_tax_not_payable[2]['taxable_value']))
        self.assertEqual(values_tax_not_payable[2]['taxable_value'], 2000.0)

        #nil_rate
        print("NIL, Expected: %d; Received: %d " % (4000, values_tax_not_payable[3]['taxable_value']))
        self.assertEqual(values_tax_not_payable[3]['taxable_value'], 4000.0)

        #6 ITC
        #inward_expt_reverse_service
        print("INWARD NOT REVERSE CHRG-SERVICE, Expected: %d; Received: %d " % (500, itc[0]['taxable_value']))
        self.assertEqual(itc[0]['taxable_value'], 500.0)
        self.assertEqual(itc[0]['igst'], 0.0)
        self.assertEqual(itc[0]['cgst'], 12.5)
        self.assertEqual(itc[0]['sgst'], 12.5)

        #inward_expt_reverse_input
        print("INWARD NOT REVERSE CHRG-PRODUCT, Expected: %d; Received: %d " % (1500, itc[1]['taxable_value']))
        self.assertEqual(itc[1]['taxable_value'], 1500.0)
        self.assertEqual(itc[1]['igst'], 50.0)
        self.assertEqual(itc[1]['cgst'], 12.5)
        self.assertEqual(itc[1]['sgst'], 12.5)

        #import_goods
        print("IMPORT PRODUCTS, Expected: %d; Received: %d " % (6000, itc[3]['taxable_value']))
        self.assertEqual(itc[3]['taxable_value'], 6000.0)
        self.assertEqual(itc[3]['igst'], 300.0)
        self.assertEqual(itc[3]['cgst'], 0.0)
        self.assertEqual(itc[3]['sgst'], 0.0)

        #import_service
        print("IMPORT SERVICE, Expected: %d; Received: %d " % (4500, itc[4]['taxable_value']))
        self.assertEqual(itc[4]['taxable_value'], 4500.0)
        self.assertEqual(itc[4]['igst'], 225.0)
        self.assertEqual(itc[4]['cgst'], 0.0)
        self.assertEqual(itc[4]['sgst'], 0.0)

        # HSN out
        hsn_out_vals = self.compute_hsn(hsn_out)
        print("HSN OUT PRODUCT A TAXABLE:, Expected: %d; Received: %d " % (1000, hsn_out_vals['Product A'][1]))
        self.assertEqual(hsn_out_vals['Product A'][1], 1000.0)
        self.assertEqual(hsn_out_vals['Product A'][2], 0.0)
        self.assertEqual(hsn_out_vals['Product A'][3], 25.0)
        self.assertEqual(hsn_out_vals['Product A'][4], 25.0)
        print("HSN OUT PRODUCT B TAXABLE:, Expected: %d; Received: %d " % (19200, hsn_out_vals['Product B'][1]))
        self.assertEqual(hsn_out_vals['Product B'][1], 19200.0)
        self.assertEqual(hsn_out_vals['Product B'][2], 660.0)
        self.assertEqual(hsn_out_vals['Product B'][3], 0.0)
        self.assertEqual(hsn_out_vals['Product B'][4], 0.0)
        print("HSN OUT PRODUCT LARGE TAXABLE:, Expected: %d; Received: %d " % (0, hsn_out_vals['Product Large'][1]))
        self.assertEqual(hsn_out_vals['Product Large'][1], 0.0)
        self.assertEqual(hsn_out_vals['Product Large'][2], 0.0)
        self.assertEqual(hsn_out_vals['Product Large'][3], 0.0)
        self.assertEqual(hsn_out_vals['Product Large'][4], 0.0)
        print("HSN OUT SERVICE1 TAXABLE:, Expected: %d; Received: %d " % (2000, hsn_out_vals['Service 1'][1]))
        self.assertEqual(hsn_out_vals['Service 1'][1], 2000.0)
        self.assertEqual(hsn_out_vals['Service 1'][2], 0.0)
        self.assertEqual(hsn_out_vals['Service 1'][3], 50.0)
        self.assertEqual(hsn_out_vals['Service 1'][4], 50.0)
        print("HSN OUT SERVICE2 TAXABLE:, Expected: %d; Received: %d " % (2000, hsn_out_vals['Service 2'][1]))
        self.assertEqual(hsn_out_vals['Service 2'][1], 2000.0)
        self.assertEqual(hsn_out_vals['Service 2'][2], 100.0)
        self.assertEqual(hsn_out_vals['Service 2'][3], 0.0)
        self.assertEqual(hsn_out_vals['Service 2'][4], 0.0)

        # HSN in
        hsn_in_vals = self.compute_hsn(hsn_in)
        print("HSN IN PRODUCT A TAXABLE:, Expected: %d; Received: %d " % (500, hsn_in_vals['Product A'][1]))
        self.assertEqual(hsn_in_vals['Product A'][1], 500.0)
        self.assertEqual(hsn_in_vals['Product A'][2], 0.0)
        self.assertEqual(hsn_in_vals['Product A'][3], 12.5)
        self.assertEqual(hsn_in_vals['Product A'][4], 12.5)
        print("HSN IN PRODUCT B TAXABLE:, Expected: %d; Received: %d " % (8000, hsn_in_vals['Product B'][1]))
        self.assertEqual(hsn_in_vals['Product B'][1], 8000.0)
        self.assertEqual(hsn_in_vals['Product B'][2], 400.0)
        self.assertEqual(hsn_in_vals['Product B'][3], 0.0)
        self.assertEqual(hsn_in_vals['Product B'][4], 0.0)
        print("HSN IN PRODUCT LARGE TAXABLE:, Expected: %d; Received: %d " % (-280000.0, hsn_in_vals['Product Large'][1]))
        self.assertEqual(hsn_in_vals['Product Large'][1], -280000.0)
        self.assertEqual(hsn_in_vals['Product Large'][2], -14000.0)
        self.assertEqual(hsn_in_vals['Product Large'][3], 0.0)
        self.assertEqual(hsn_in_vals['Product Large'][4], 0.0)
        print("HSN IN SERVICE1 TAXABLE:, Expected: %d; Received: %d " % (1000, hsn_in_vals['Service 1'][1]))
        self.assertEqual(hsn_in_vals['Service 1'][1], 1000.0)
        self.assertEqual(hsn_in_vals['Service 1'][2], 0.0)
        self.assertEqual(hsn_in_vals['Service 1'][3], 25.0)
        self.assertEqual(hsn_in_vals['Service 1'][4], 25.0)
        print("HSN IN SERVICE2 TAXABLE:, Expected: %d; Received: %d " % (9000, hsn_in_vals['Service 2'][1]))
        self.assertEqual(hsn_in_vals['Service 2'][1], 4500.0)
        self.assertEqual(hsn_in_vals['Service 2'][2], 225.0)
        self.assertEqual(hsn_in_vals['Service 2'][3], 0.0)
        self.assertEqual(hsn_in_vals['Service 2'][4], 0.0)

    def compute_hsn(self, hsn_vals):
        hsn_vals_updated = {}
        for product_hsn, hsn_sum in sorted(hsn_vals.items(), key=lambda p: p[0].name):
            vals = []
            vals.append(hsn_sum[0])  # hsn quantity
            vals.append(hsn_sum[1])  # taxable value
            vals.append(hsn_sum[2])  # igst
            vals.append(hsn_sum[3])  # cgst
            vals.append(hsn_sum[4])  # sgst
            vals.append(hsn_sum[5])  # cess
            hsn_vals_updated[product_hsn.name] = vals
        return hsn_vals_updated