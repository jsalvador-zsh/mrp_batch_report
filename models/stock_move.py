from odoo import models, fields


class StockMove(models.Model):
    _inherit = 'stock.move'

    is_dosimetria = fields.Boolean(
        string='Es Dosimetría',
        default=False,
        help='Si está marcado, este componente será considerado como dosimetría en el reporte PDF. Sus porcentajes se sumarán y no se mostrará en la tabla de componentes.'
    )
