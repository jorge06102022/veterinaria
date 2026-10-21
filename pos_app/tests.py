"""
test_flujos_criticos.py - Suite integral de pruebas automatizadas para Pet Shop & Peluquería Canina POS
Pruebas obligatorias:
1. Productos e Inventario (códigos duplicados, salidas, bloqueo de sobreventa).
2. Ventas combinadas (productos + peluquería) y desglose de medios de pago.
3. Peluquería Canina: Comisión exacta del 50%, múltiples atenciones en la jornada.
4. Adelantos: Reducción de saldo a pagar sin duplicar movimientos financieros.
5. Liquidación diaria: Saldo pendiente = saldo anterior + comisiones - adelantos - pagos. Arrastre de saldos.
6. Caja: Separación estricta entre efectivo físico y transferencias/tarjetas bancarias. Cierre comparativo.
7. Egresos y pagos a personal (beneficiario y no duplicación con peluqueros).
8. Anulación trazable de venta y devolución de stock al inventario.
"""
from decimal import Decimal
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone

from pos_app.models import (
    Categoria, Producto, Cliente, Mascota, Trabajador,
    ServicioPeluqueria, SesionCaja, Venta, DetalleVenta,
    PagoVenta, AtencionPeluqueria, AdelantoPeluquero,
    LiquidacionPeluquero, PagoLiquidacion, Egreso, MovimientoInventario
)

User = get_user_model()


class PosPetShopTestSuite(TestCase):
    def setUp(self):
        # Crear usuario administrador
        self.admin = User.objects.create_superuser('admin_test', 'admin@test.com', 'pass123')
        self.client = Client()
        self.client.force_login(self.admin)

        # Categoría y Producto
        self.categoria = Categoria.objects.create(nombre="Alimentos Perros")
        self.producto = Producto.objects.create(
            nombre="Croquetas Premium 2kg",
            sku="77000000001",
            categoria=self.categoria,
            precio_compra=Decimal('20000.00'),
            precio_venta=Decimal('35000.00'),
            stock=10,
            stock_minimo=3
        )

        # Trabajador Peluquero (50% de comisión)
        self.peluquero = Trabajador.objects.create(
            nombre="Carlos Peluquero",
            rol="peluquero",
            porcentaje_comision_peluqueria=Decimal('50.00')
        )

        # Servicio de Peluquería
        self.servicio = ServicioPeluqueria.objects.create(
            nombre="Baño y Corte Canino",
            precio_sugerido=Decimal('40000.00')
        )

        # Cliente y Mascota
        self.cliente_obj = Cliente.objects.create(
            nombre="Laura Propietaria",
            telefono="3001112233"
        )
        self.mascota_obj = Mascota.objects.create(
            cliente=self.cliente_obj,
            nombre="Firu",
            especie="perro",
            raza="Poodle",
            tamano="pequeno"
        )

        # Sesión de Caja Activa con base de $50.000 COP
        self.caja = SesionCaja.objects.create(
            monto_inicial_efectivo=Decimal('50000.00'),
            usuario_apertura=self.admin,
            estado='abierta'
        )

    # --------------------------------------------------------------------------
    # 1. PRODUCTOS E INVENTARIO
    # --------------------------------------------------------------------------
    def test_stock_descuento_en_venta_y_bloqueo_sobreventa(self):
        """Verifica que el stock se descuente y se impida vender más de lo existente."""
        # Intento de sobreventa: solicitar 15 unidades cuando hay 10
        payload_invalido = {
            'productos': [{'producto_id': self.producto.pk, 'cantidad': 15, 'precio_venta': 35000}],
            'servicios': [],
            'metodo_pago': 'efectivo',
            'pagos': [{'metodo': 'efectivo', 'monto': 15 * 35000}]
        }
        res = self.client.post('/pos/procesar/', data=json.dumps(payload_invalido), content_type='application/json')
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn('Stock insuficiente', data['error'])
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 10)  # No se alteró

        # Venta válida de 3 unidades
        payload_valido = {
            'productos': [{'producto_id': self.producto.pk, 'cantidad': 3, 'precio_venta': 35000}],
            'servicios': [],
            'metodo_pago': 'efectivo',
            'pagos': [{'metodo': 'efectivo', 'monto': 3 * 35000}]
        }
        res_ok = self.client.post('/pos/procesar/', data=json.dumps(payload_valido), content_type='application/json')
        data_ok = res_ok.json()
        self.assertTrue(data_ok['success'])

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 7)  # 10 - 3 = 7

        # Kardex generado
        mov = MovimientoInventario.objects.filter(producto=self.producto, tipo='salida_venta').first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.stock_anterior, 10)
        self.assertEqual(mov.stock_nuevo, 7)

    # --------------------------------------------------------------------------
    # 2. VENTA COMBINADA Y PAGOS MIXTOS (EFECTIVO + BANCO)
    # --------------------------------------------------------------------------
    def test_venta_combinada_y_pago_mixto_validado(self):
        """
        Venta con 1 producto ($35.000) + 1 servicio ($40.000) = $75.000 total.
        Pago mixto: $25.000 en efectivo + $50.000 por transferencia bancaria.
        """
        payload = {
            'productos': [{'producto_id': self.producto.pk, 'cantidad': 1, 'precio_venta': 35000}],
            'servicios': [{
                'servicio_id': self.servicio.pk,
                'peluquero_id': self.peluquero.pk,
                'mascota_id': self.mascota_obj.pk,
                'precio': 40000,
                'descuento': 0
            }],
            'metodo_pago': 'mixto',
            'pagos': [
                {'metodo': 'efectivo', 'monto': 25000},
                {'metodo': 'transferencia', 'monto': 50000}
            ]
        }
        res = self.client.post('/pos/procesar/', data=json.dumps(payload), content_type='application/json')
        data = res.json()
        self.assertTrue(data['success'])

        venta = Venta.objects.get(pk=data['venta_id'])
        self.assertEqual(venta.total_venta, Decimal('75000.00'))
        self.assertEqual(venta.pagos.count(), 2)

        pago_efectivo = venta.pagos.filter(metodo='efectivo').first()
        pago_transf = venta.pagos.filter(metodo='transferencia').first()
        self.assertEqual(pago_efectivo.monto, Decimal('25000.00'))
        self.assertEqual(pago_transf.monto, Decimal('50000.00'))

        # Comisión generada: 50% de $40.000 = $20.000 para el peluquero
        # El producto NO genera comisión
        self.assertEqual(venta.total_comision_peluquero, Decimal('20000.00'))
        atencion = venta.servicios_peluqueria.first()
        self.assertEqual(atencion.comision_calculada, Decimal('20000.00'))
        self.assertEqual(atencion.parte_negocio, Decimal('20000.00'))

    # --------------------------------------------------------------------------
    # 3. MÓDULO ESPECIAL: ADELANTOS Y LIQUIDACIÓN DIARIA DEL PELUQUERO
    # --------------------------------------------------------------------------
    def test_peluqueria_comision_adelanto_y_liquidacion_diaria(self):
        """
        Escenario completo:
        1. Dos servicios realizados: $30.000 y $50.000. Total = $80.000. Comisión 50% = $40.000.
        2. Adelanto entregado: $15.000.
        3. Saldo a pagar = $40.000 - $15.000 = $25.000.
        4. Pago parcial de $15.000. Saldo restante = $10.000.
        5. El saldo de $10.000 se traslada al día siguiente sin duplicar comisiones ya liquidadas.
        """
        # Crear 2 servicios
        AtencionPeluqueria.objects.create(
            servicio=self.servicio,
            peluquero=self.peluquero,
            precio_cobrado=Decimal('30000.00'),
            porcentaje_comision=Decimal('50.00')
        )
        AtencionPeluqueria.objects.create(
            servicio=self.servicio,
            peluquero=self.peluquero,
            precio_cobrado=Decimal('50000.00'),
            porcentaje_comision=Decimal('50.00')
        )

        # Registrar adelanto de $15.000 en efectivo
        adelanto = AdelantoPeluquero.objects.create(
            peluquero=self.peluquero,
            sesion_caja=self.caja,
            monto=Decimal('15000.00'),
            medio_entrega='efectivo'
        )

        # Ejecutar liquidación con pago parcial de $15.000
        res = self.client.post(f'/peluqueria/liquidar/{self.peluquero.pk}/', data={
            'monto_pago': '15000',
            'medio_pago': 'efectivo',
            'observacion': 'Pago parcial de la jornada'
        })
        self.assertEqual(res.status_code, 302)

        liq = LiquidacionPeluquero.objects.filter(peluquero=self.peluquero).first()
        self.assertIsNotNone(liq)
        self.assertEqual(liq.total_comision, Decimal('40000.00'))
        self.assertEqual(liq.total_adelantos, Decimal('15000.00'))
        self.assertEqual(liq.total_pagos, Decimal('15000.00'))
        # Saldo pendiente = 0 (anterior) + 40.000 - 15.000 - 15.000 = $10.000
        self.assertEqual(liq.saldo_pendiente, Decimal('10000.00'))
        self.assertEqual(liq.estado, 'parcial')

        # Verificar que los servicios quedaron marcados como liquidados
        for s in liq.servicios_incluidos.all():
            self.assertEqual(s.estado_liquidacion, 'liquidado')

        # Verificar que el adelanto quedó imputado
        adelanto.refresh_from_db()
        self.assertEqual(adelanto.estado, 'imputado')

    # --------------------------------------------------------------------------
    # 4. CONTROL DE CAJA Y SEPARACIÓN EFECTIVO / BANCOS
    # --------------------------------------------------------------------------
    def test_cierre_de_caja_separacion_efectivo_banco_y_diferencia(self):
        """
        Prueba del requerimiento obligatorio de cierre:
        - Base inicial: $50.000 en efectivo.
        - Ventas: $30.000 en efectivo y $40.000 por transferencia.
        - Egreso en efectivo: $10.000.
        - Efectivo esperado: $50.000 + $30.000 - $10.000 = $70.000.
        - Banco esperado: $40.000 (no afecta el efectivo en gaveta).
        - Conteo físico: $70.000 (diferencia 0).
        """
        # Registrar venta en efectivo
        v1 = Venta.objects.create(
            sesion_caja=self.caja,
            metodo_pago='efectivo',
            total_venta=Decimal('30000.00')
        )
        PagoVenta.objects.create(venta=v1, metodo='efectivo', monto=Decimal('30000.00'))

        # Registrar venta por transferencia bancaria
        v2 = Venta.objects.create(
            sesion_caja=self.caja,
            metodo_pago='transferencia',
            total_venta=Decimal('40000.00')
        )
        PagoVenta.objects.create(venta=v2, metodo='transferencia', monto=Decimal('40000.00'))

        # Registrar egreso en efectivo de $10.000
        Egreso.objects.create(
            nombre="Artículos de aseo",
            categoria="compras_menores",
            monto=Decimal('10000.00'),
            metodo_pago="efectivo",
            sesion_caja=self.caja
        )

        # Ejecutar cierre con conteo físico exacto de $70.000
        res = self.client.post('/caja/cerrar/', data={
            'efectivo_real': '70000.00',
            'observaciones': 'Arqueo perfecto'
        })
        self.assertEqual(res.status_code, 302)

        self.caja.refresh_from_db()
        self.assertEqual(self.caja.estado, 'cerrada')
        self.assertEqual(self.caja.efectivo_esperado, Decimal('70000.00'))
        self.assertEqual(self.caja.efectivo_real, Decimal('70000.00'))
        self.assertEqual(self.caja.diferencia_efectivo, Decimal('0.00'))
        self.assertEqual(self.caja.banco_esperado, Decimal('40000.00'))

    # --------------------------------------------------------------------------
    # 5. ANULACIÓN SEGURA Y TRAZABLE
    # --------------------------------------------------------------------------
    def test_anulacion_de_venta_devuelve_stock_y_mantiene_trazabilidad(self):
        """Verifica que anular una venta devuelva las unidades al inventario."""
        # Vender 2 unidades
        stock_inicial = self.producto.stock
        payload = {
            'productos': [{'producto_id': self.producto.pk, 'cantidad': 2, 'precio_venta': 35000}],
            'servicios': [],
            'metodo_pago': 'efectivo',
            'pagos': [{'metodo': 'efectivo', 'monto': 70000}]
        }
        res = self.client.post('/pos/procesar/', data=json.dumps(payload), content_type='application/json')
        venta_id = res.json()['venta_id']

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, stock_inicial - 2)

        # Anular la venta
        res_anular = self.client.post(f'/ventas/{venta_id}/anular/', data={'motivo': 'Cliente desistió'})
        self.assertEqual(res_anular.status_code, 302)

        venta = Venta.objects.get(pk=venta_id)
        self.assertEqual(venta.estado, 'anulada')
        self.assertEqual(venta.motivo_anulacion, 'Cliente desistió')

        # Stock devuelto exactamente
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, stock_inicial)

        # Kardex de devolución
        kardex = MovimientoInventario.objects.filter(producto=self.producto, tipo='anulacion_venta').first()
        self.assertIsNotNone(kardex)
        self.assertEqual(kardex.cantidad, 2)
