from odoo import models, fields, api
import math


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    batch_size = fields.Float(
        string='Cantidad por Batch',
        default=300.0,
        help='Cantidad de producto a producir por batch'
    )
    
    batch_count = fields.Integer(
        string='Número de Batches',
        compute='_compute_batch_count',
        store=True,
        help='Número total de batches calculado automáticamente'
    )
    
    batch_details = fields.Text(
        string='Detalle de Batches',
        compute='_compute_batch_details',
        store=True
    )
    
    # Campos adicionales para el reporte
    lote_produccion = fields.Char(string='Lote')
    numero_pedido = fields.Char(string='Número de Pedido')
    envase_primario = fields.Char(string='Envase Primario')
    lote_envase = fields.Char(string='Lote de Envase Primario')
    tipo_envase = fields.Char(string='Tipo de Envase')
    municipalidad = fields.Char(string='Municipalidad')
    registro_sanitario = fields.Char(string='Registro Sanitario')
    kg_neto = fields.Float(string='KG Neto', compute='_compute_kg_neto', store=True)
    kg_bruto = fields.Float(string='KG Bruto', compute='_compute_kg_bruto', store=True)
    codigo_equipo = fields.Char(string='Código de Equipo')
    conformidad = fields.Selection([
        ('conforme', 'Conforme'),
        ('no_conforme', 'No Conforme')
    ], string='Conformidad', default='conforme')
    observaciones = fields.Text(string='Observaciones y/o Acción Correctiva')

    @api.depends('product_qty', 'batch_size')
    def _compute_batch_count(self):
        for record in self:
            if record.batch_size > 0:
                record.batch_count = math.ceil(record.product_qty / record.batch_size)
            else:
                record.batch_count = 0

    @api.depends('product_qty', 'batch_size', 'batch_count')
    def _compute_batch_details(self):
        for record in self:
            if record.batch_size > 0 and record.batch_count > 0:
                details = []
                remaining = record.product_qty
                
                for i in range(record.batch_count):
                    batch_number = i + 1  # 1, 2, 3, etc.
                    batch_qty = min(record.batch_size, remaining)
                    details.append(f"Batch {batch_number}: {batch_qty:.2f} kg")
                    remaining -= batch_qty
                
                record.batch_details = '\n'.join(details)
            else:
                record.batch_details = ''

    @api.depends('product_qty')
    def _compute_kg_neto(self):
        for record in self:
            # Asumiendo que product_qty está en kg
            record.kg_neto = record.product_qty

    @api.depends('kg_neto')
    def _compute_kg_bruto(self):
        for record in self:
            # Agregando un 0.5% de peso adicional para el bruto
            record.kg_bruto = record.kg_neto * 1.005

    def get_mix_columns_rows(self):
        """
        Calcula cuántas filas de columnas se necesitan para las mezclas
        Calcula dinámicamente cuántas columnas caben por fila según el ancho disponible
        En A4 horizontal tenemos ~270mm disponibles
        Columnas fijas: MATERIA PRIMA(40mm) + %(15mm) + KG/BATCH(20mm) + LOTE(25mm) + OBS(30mm) = 130mm
        Espacio para mezclas: ~140mm
        Cada columna de mezcla: ~3.5mm
        Columnas que caben: ~40 columnas de mezcla por fila
        """
        self.ensure_one()
        total_batches = self.batch_count
        max_cols_per_row = 40  # Ajustado para A4 horizontal
        
        rows = []
        remaining = total_batches
        start = 1
        
        while remaining > 0:
            cols_in_row = min(max_cols_per_row, remaining)
            end = start + cols_in_row - 1
            rows.append({
                'start': start,
                'end': end,
                'count': cols_in_row,
                'columns': list(range(start, end + 1))
            })
            remaining -= cols_in_row
            start = end + 1
        
        return rows

    def get_batch_data_grouped(self):
        """
        Retorna la información de batches AGRUPADOS por cantidad
        Los batches con la misma cantidad se agrupan juntos
        """
        self.ensure_one()
        grouped_batches = []
        
        if self.batch_size <= 0:
            return grouped_batches
        
        remaining = self.product_qty
        batch_quantities = []
        
        # Primero calcular todas las cantidades de batch
        for i in range(self.batch_count):
            batch_qty = min(self.batch_size, remaining)
            batch_quantities.append(batch_qty)
            remaining -= batch_qty
        
        # Agrupar batches por cantidad
        from collections import OrderedDict
        grouped = OrderedDict()
        
        for i, qty in enumerate(batch_quantities):
            batch_number = i + 1  # 1, 2, 3, etc.
            
            # Usar la cantidad como clave para agrupar
            qty_key = round(qty, 2)
            
            if qty_key not in grouped:
                grouped[qty_key] = {
                    'quantity': qty,
                    'count': 0,
                    'numbers': [],
                    'batch_numbers': []
                }
            
            grouped[qty_key]['count'] += 1
            grouped[qty_key]['numbers'].append(batch_number)
            grouped[qty_key]['batch_numbers'].append(i + 1)
        
        # Convertir a lista con componentes calculados
        for qty_key, batch_group in grouped.items():
            # Calcular componentes para esta cantidad de batch
            components = []
            total_component_weight = 0
            
            for move in self.move_raw_ids:
                if move.product_id and move.product_uom_qty > 0:
                    # Calcular la cantidad proporcional para este batch
                    component_qty = (batch_group['quantity'] / self.product_qty) * move.product_uom_qty
                    component_percentage = (component_qty / batch_group['quantity']) * 100 if batch_group['quantity'] > 0 else 0
                    
                    # Obtener el lote asignado a este movimiento
                    lote = ''
                    if move.lot_ids:
                        # Si hay lotes asignados, tomar el primero
                        lote = move.lot_ids[0].name
                    elif move.move_line_ids:
                        # Si hay líneas de movimiento con lote
                        lotes = move.move_line_ids.mapped('lot_id.name')
                        lote = ', '.join(filter(None, lotes))
                    
                    components.append({
                        'name': move.product_id.name,
                        'code': move.product_id.default_code or '',
                        'quantity': component_qty,
                        'percentage': component_percentage,
                        'uom': move.product_uom.name,
                        'lote': lote,
                    })
                    
                    total_component_weight += component_qty
            
            # Crear descripción de números
            if batch_group['count'] == 1:
                numbers_desc = str(batch_group['numbers'][0])
            else:
                numbers_desc = ', '.join([str(n) for n in batch_group['numbers']])
            
            grouped_batches.append({
                'numbers': numbers_desc,
                'count': batch_group['count'],
                'quantity': batch_group['quantity'],
                'components': components,
                'total_weight': total_component_weight,
                'is_multiple': batch_group['count'] > 1,
            })
        
        return grouped_batches