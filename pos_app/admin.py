"""
admin.py - Registro completo en el panel administrativo de Django
Permite al administrador auditar y gestionar todos los módulos del Pet Shop & Peluquería Canina.
"""
from django.contrib import admin
from .models import (
    Categoria, Producto, MovimientoInventario,
    Cliente, Mascota, Trabajador, ServicioPeluqueria,
    SesionCaja, Venta, DetalleVenta, PagoVenta, AtencionPeluqueria,
    AdelantoPeluquero, LiquidacionPeluquero, PagoLiquidacion,
    Proveedor, Compra, DetalleCompra, Egreso
)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion', 'fecha_creacion']
    search_fields = ['nombre']


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'sku', 'codigo_interno', 'categoria', 'precio_compra', 'precio_venta', 'stock', 'unidad_medida', 'activo']
    list_filter = ['activo', 'categoria', 'unidad_medida']
    search_fields = ['nombre', 'sku', 'codigo_interno']
    list_editable = ['stock', 'activo']


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'producto', 'tipo', 'cantidad', 'stock_anterior', 'stock_nuevo', 'referencia_origen', 'usuario']
    list_filter = ['tipo', 'fecha']
    search_fields = ['producto__nombre', 'referencia_origen', 'motivo']


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'telefono', 'documento', 'direccion', 'fecha_registro']
    search_fields = ['nombre', 'telefono', 'documento']


@admin.register(Mascota)
class MascotaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'cliente', 'especie', 'raza', 'tamano', 'activo']
    list_filter = ['especie', 'tamano', 'activo']
    search_fields = ['nombre', 'cliente__nombre', 'raza']


@admin.register(Trabajador)
class TrabajadorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'rol', 'telefono', 'porcentaje_comision_peluqueria', 'activo']
    list_filter = ['rol', 'activo']
    search_fields = ['nombre', 'telefono', 'documento']


@admin.register(ServicioPeluqueria)
class ServicioPeluqueriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'precio_sugerido', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre']


@admin.register(SesionCaja)
class SesionCajaAdmin(admin.ModelAdmin):
    list_display = ['pk', 'fecha_apertura', 'fecha_cierre', 'monto_inicial_efectivo', 'efectivo_esperado', 'efectivo_real', 'diferencia_efectivo', 'banco_esperado', 'estado']
    list_filter = ['estado', 'fecha_apertura']


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0
    readonly_fields = ['subtotal']


class PagoVentaInline(admin.TabularInline):
    model = PagoVenta
    extra = 0


class AtencionPeluqueriaInline(admin.TabularInline):
    model = AtencionPeluqueria
    extra = 0
    fields = ['servicio', 'peluquero', 'mascota', 'precio_cobrado', 'comision_calculada', 'estado_liquidacion']
    readonly_fields = ['comision_calculada']


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ['pk', 'fecha', 'cliente', 'total_venta', 'total_ganancia', 'metodo_pago', 'estado']
    list_filter = ['estado', 'metodo_pago', 'fecha']
    inlines = [DetalleVentaInline, AtencionPeluqueriaInline, PagoVentaInline]
    search_fields = ['pk', 'cliente__nombre']


@admin.register(AdelantoPeluquero)
class AdelantoPeluqueroAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'peluquero', 'monto', 'medio_entrega', 'estado', 'sesion_caja']
    list_filter = ['medio_entrega', 'estado', 'fecha']
    search_fields = ['peluquero__nombre', 'motivo']


class PagoLiquidacionInline(admin.TabularInline):
    model = PagoLiquidacion
    extra = 0


@admin.register(LiquidacionPeluquero)
class LiquidacionPeluqueroAdmin(admin.ModelAdmin):
    list_display = ['fecha_jornada', 'peluquero', 'total_comision', 'total_adelantos', 'total_pagos', 'saldo_pendiente', 'estado']
    list_filter = ['estado', 'fecha_jornada']
    inlines = [PagoLiquidacionInline]
    search_fields = ['peluquero__nombre']


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'contacto', 'telefono', 'nit', 'activo']
    search_fields = ['nombre', 'nit', 'contacto']


class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 0


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ['pk', 'fecha', 'proveedor', 'total', 'metodo_pago', 'estado']
    list_filter = ['estado', 'metodo_pago', 'fecha']
    inlines = [DetalleCompraInline]
    search_fields = ['proveedor__nombre', 'numero_factura_proveedor']


@admin.register(Egreso)
class EgresoAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'nombre', 'categoria', 'beneficiario', 'monto', 'metodo_pago', 'sesion_caja']
    list_filter = ['categoria', 'metodo_pago', 'fecha']
    search_fields = ['nombre', 'beneficiario']
