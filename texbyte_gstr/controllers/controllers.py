# -*- coding: utf-8 -*-
from odoo import http

# class TexbyteGst(http.Controller):
#     @http.route('/texbyte_gstr/texbyte_gstr/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/texbyte_gstr/texbyte_gstr/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('texbyte_gstr.listing', {
#             'root': '/texbyte_gstr/texbyte_gstr',
#             'objects': http.request.env['texbyte_gstr.texbyte_gstr'].search([]),
#         })

#     @http.route('/texbyte_gstr/texbyte_gstr/objects/<model("texbyte_gstr.texbyte_gstr"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('texbyte_gstr.object', {
#             'object': obj
#         })