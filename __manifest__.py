{
    'name': 'MRP Batch Production Report',
    'version': '18.0.2.3.0',
    'category': 'Manufacturing',
    'summary': 'Reporte de producción por batches con cálculo de componentes',
    'description': """
        Módulo para gestionar producción por batches:
        - Campo para definir cantidad por batch
        - Cálculo automático de número de batches
        - Reporte PDF detallado por batch con componentes
    """,
    'author': 'Peruanita E.I.R.L.',
    'depends': ['mrp', 'product'],
    'data': [
        'views/mrp_production_views.xml',
        'reports/mrp_batch_report.xml',
        'reports/mrp_batch_report_template.xml',
        'reports/mrp_batch_dosimetria_report.xml',
        'reports/mrp_batch_dosimetria_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}