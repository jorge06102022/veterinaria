"""
urls.py - Enrutamiento completo de la aplicación POS Pet Shop y Peluquería Canina
"""
from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard, name='dashboard'),

    # Inventario y Productos
    path('inventario/', views.inventario, name='inventario'),
    path('inventario/nuevo/', views.producto_crear, name='producto_crear'),
    path('inventario/<int:pk>/editar/', views.producto_editar, name='producto_editar'),
    path('inventario/<int:pk>/eliminar/', views.producto_eliminar, name='producto_eliminar'),
    path('inventario/<int:pk>/', views.producto_detalle, name='producto_detalle'),

    # Punto de Venta (POS)
    path('pos/', views.pos, name='pos'),
    path('pos/procesar/', views.procesar_venta, name='procesar_venta'),
    path('api/productos/', views.api_buscar_producto, name='api_productos'),

    # Ventas e Historial
    path('ventas/', views.historial_ventas, name='historial_ventas'),
    path('ventas/<int:pk>/', views.venta_detalle, name='venta_detalle'),
    path('ventas/<int:pk>/anular/', views.anular_venta, name='anular_venta'),

    # Peluquería de Mascotas, Comisiones y Liquidaciones
    path('peluqueria/', views.peluqueria_dashboard, name='peluqueria_dashboard'),
    path('peluqueria/adelanto/', views.adelanto_registrar, name='adelanto_registrar'),
    path('peluqueria/liquidar/<int:peluquero_id>/', views.liquidacion_jornada, name='liquidacion_jornada'),

    # Clientes y Mascotas
    path('clientes/', views.clientes_list, name='clientes_list'),
    path('clientes/nuevo/', views.cliente_crear, name='cliente_crear'),
    path('clientes/<int:pk>/', views.cliente_detalle, name='cliente_detalle'),
    path('clientes/<int:pk>/editar/', views.cliente_editar, name='cliente_editar'),
    path('mascotas/nueva/', views.mascota_crear, name='mascota_crear'),
    path('clientes/<int:cliente_id>/mascotas/nueva/', views.mascota_crear, name='cliente_mascota_crear'),

    # Caja: Apertura, Cierre y Control de Efectivo vs Banco
    path('caja/', views.caja_detalle, name='caja_detalle'),
    path('caja/abrir/', views.caja_abrir, name='caja_abrir'),
    path('caja/cerrar/', views.caja_cerrar, name='caja_cerrar'),

    # Compras a Proveedores
    path('compras/', views.compras_list, name='compras_list'),
    path('compras/nueva/', views.compra_registrar, name='compra_registrar'),

    # Egresos Operativos y Pagos al Personal
    path('egresos/', views.egresos_list_create, name='egresos_list_create'),
    path('egresos/<int:pk>/', views.egreso_detail, name='egreso_detail'),
    path('egresos/registrar/', views.egresos_page, name='egresos_page'),
    path('egresos/guardar/', views.egresos_guardar, name='egresos_guardar'),
    path('eliminar-egresos/', views.eliminar_egresos, name='eliminar_egresos'),

    # Reportes Financieros y Ganancia Estimada
    path('reportes/', views.reportes, name='reportes'),
    path('reporte-diario/', views.reporte_diario_pdf, name='reporte_diario'),
    path('api/stock-bajo/', views.api_stock_bajo, name='api_stock_bajo'),

    # Contingencia y Sesión
    path('crear-admin/', views.crear_admin, name='crear_admin'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
