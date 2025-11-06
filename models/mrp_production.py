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
                # Usar product_qty (cantidad planificada) en lugar de qty_producing
                record.batch_count = math.ceil(record.product_qty / record.batch_size)
            else:
                record.batch_count = 0

    @api.depends('product_qty', 'batch_size', 'batch_count')
    def _compute_batch_details(self):
        for record in self:
            if record.batch_size > 0 and record.batch_count > 0:
                details = []
                # Usar product_qty (cantidad planificada) en lugar de qty_producing
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
            # Usar product_qty (cantidad planificada) en lugar de qty_producing
            record.kg_neto = record.product_qty

    @api.depends('kg_neto')
    def _compute_kg_bruto(self):
        for record in self:
            # Agregando un 0.5% de peso adicional para el bruto
            record.kg_bruto = record.kg_neto * 1.005

    def debug_lots_info(self):
        """
        Método de depuración para verificar el estado de los lotes
        """
        self.ensure_one()
        info = []
        info.append(f"=== DEBUG LOTES - Orden: {self.name} ===")
        info.append(f"Estado: {self.state}")
        info.append(f"Movimientos raw: {len(self.move_raw_ids)}")

        for move in self.move_raw_ids:
            info.append(f"\nComponente: {move.product_id.name}")
            info.append(f"  - Estado del move: {move.state}")
            info.append(f"  - Cantidad: {move.product_uom_qty}")
            info.append(f"  - Líneas de movimiento: {len(move.move_line_ids)}")

            for line in move.move_line_ids:
                info.append(f"    * Línea ID: {line.id}")
                info.append(f"      - Lote: {line.lot_id.name if line.lot_id else 'SIN LOTE'}")
                info.append(f"      - Cantidad reservada: {line.reserved_uom_qty}")
                info.append(f"      - Cantidad hecha: {line.qty_done}")
                info.append(f"      - Estado: {line.state if hasattr(line, 'state') else 'N/A'}")

        return '\n'.join(info)

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

        # Usar product_qty (cantidad planificada) en lugar de qty_producing
        # para evitar división por cero cuando aún no se ha comenzado a producir
        total_qty = self.product_qty if self.product_qty > 0 else self.qty_producing

        if total_qty <= 0:
            return grouped_batches

        remaining = total_qty
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
            dosimetria_components = []
            total_component_weight = 0
            total_dosimetria_percentage = 0
            total_dosimetria_kg = 0

            for move in self.move_raw_ids:
                if move.product_id and move.product_uom_qty > 0:
                    # Calcular la cantidad proporcional para este batch
                    component_qty = (batch_group['quantity'] / total_qty) * move.product_uom_qty
                    component_percentage = (component_qty / batch_group['quantity']) * 100 if batch_group['quantity'] > 0 else 0

                    # Obtener el lote asignado a este movimiento
                    lote = ''
                    if move.move_line_ids:
                        # Si hay líneas de movimiento con lote
                        # Filtrar líneas que tengan lote asignado
                        lotes_list = []
                        for line in move.move_line_ids:
                            if line.lot_id:
                                lotes_list.append(line.lot_id.name)

                        # Unir todos los lotes encontrados
                        if lotes_list:
                            lote = ', '.join(lotes_list)

                    # Si aún no hay lote, intentar obtener del move.lot_producing_id (para productos terminados)
                    if not lote and hasattr(move, 'lot_producing_id') and move.lot_producing_id:
                        lote = move.lot_producing_id.name

                    component_data = {
                        'name': move.product_id.name,
                        'code': move.product_id.default_code or '',
                        'quantity': component_qty,
                        'percentage': component_percentage,
                        'uom': move.product_uom.name,
                        'lote': lote,
                    }

                    # Separar componentes normales de dosimetría
                    is_dosimetria = hasattr(move, 'is_dosimetria') and move.is_dosimetria

                    if is_dosimetria:
                        dosimetria_components.append(component_data)
                        total_dosimetria_percentage += component_percentage
                        total_dosimetria_kg += component_qty
                    else:
                        components.append(component_data)

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
                'dosimetria_components': dosimetria_components,
                'total_dosimetria_percentage': total_dosimetria_percentage,
                'total_dosimetria_kg': total_dosimetria_kg,
                'total_weight': total_component_weight,
                'is_multiple': batch_group['count'] > 1,
            })

        return grouped_batches

    def get_batch_data_grouped_dosimetria(self):
        """
        Retorna la información de batches para el reporte de DOSIMETRÍA
        Los componentes CON is_dosimetria se muestran desglosados
        Los componentes SIN is_dosimetria se agrupan en "MEZCLA MATERIA"
        """
        self.ensure_one()
        grouped_batches = []

        if self.batch_size <= 0:
            return grouped_batches

        # Usar product_qty (cantidad planificada) en lugar de qty_producing
        # para evitar división por cero cuando aún no se ha comenzado a producir
        total_qty = self.product_qty if self.product_qty > 0 else self.qty_producing

        if total_qty <= 0:
            return grouped_batches

        remaining = total_qty
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

        # Convertir a lista con componentes calculados (INVERTIDO)
        for qty_key, batch_group in grouped.items():
            # Calcular componentes para esta cantidad de batch
            dosimetria_components = []  # Ahora estos se desglosan
            mezcla_materia_components = []  # Ahora estos se agrupan
            total_component_weight = 0
            total_mezcla_materia_percentage = 0
            total_mezcla_materia_kg = 0

            for move in self.move_raw_ids:
                if move.product_id and move.product_uom_qty > 0:
                    # Calcular la cantidad proporcional para este batch
                    component_qty = (batch_group['quantity'] / total_qty) * move.product_uom_qty
                    component_percentage = (component_qty / batch_group['quantity']) * 100 if batch_group['quantity'] > 0 else 0

                    # Obtener el lote asignado a este movimiento
                    lote = ''
                    if move.move_line_ids:
                        # Si hay líneas de movimiento con lote
                        # Filtrar líneas que tengan lote asignado
                        lotes_list = []
                        for line in move.move_line_ids:
                            if line.lot_id:
                                lotes_list.append(line.lot_id.name)

                        # Unir todos los lotes encontrados
                        if lotes_list:
                            lote = ', '.join(lotes_list)

                    # Si aún no hay lote, intentar obtener del move.lot_producing_id (para productos terminados)
                    if not lote and hasattr(move, 'lot_producing_id') and move.lot_producing_id:
                        lote = move.lot_producing_id.name

                    component_data = {
                        'name': move.product_id.name,
                        'code': move.product_id.default_code or '',
                        'quantity': component_qty,
                        'percentage': component_percentage,
                        'uom': move.product_uom.name,
                        'lote': lote,
                    }

                    # INVERTIDO: Separar dosimetría (desglosada) de mezcla materia (agrupada)
                    is_dosimetria = hasattr(move, 'is_dosimetria') and move.is_dosimetria

                    if is_dosimetria:
                        # Los componentes de dosimetría se desglosan
                        dosimetria_components.append(component_data)
                    else:
                        # Los componentes normales se agrupan en "MEZCLA MATERIA"
                        mezcla_materia_components.append(component_data)
                        total_mezcla_materia_percentage += component_percentage
                        total_mezcla_materia_kg += component_qty

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
                'dosimetria_components': dosimetria_components,  # Ahora desglosados
                'mezcla_materia_components': mezcla_materia_components,  # Ahora agrupados
                'total_mezcla_materia_percentage': total_mezcla_materia_percentage,
                'total_mezcla_materia_kg': total_mezcla_materia_kg,
                'total_weight': total_component_weight,
                'is_multiple': batch_group['count'] > 1,
            })

        return grouped_batches