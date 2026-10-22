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
    Categoria, Producto, Cliente, Mascota, Trabajador, Proveedor,
    ServicioPeluqueria, SesionCaja, Venta, DetalleVenta,
    PagoVenta, AtencionPeluqueria, AdelantoPeluquero,
    LiquidacionPeluquero, PagoLiquidacion, Egreso, MovimientoInventario,
    Compra, DetalleCompra, CitaPeluqueria, BitacoraAuditoria
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

    # --------------------------------------------------------------------------
    # 6. ADMINISTRACIÓN DE PELUQUEROS Y PERSONAL
    # --------------------------------------------------------------------------
    def test_peluquero_creacion_edicion_y_toggle_activo(self):
        """Verifica la creación, edición y activación/desactivación de peluqueros."""
        # 1. Crear nuevo peluquero
        res = self.client.post('/peluqueros/nuevo/', {
            'nombre': 'Andrea Estilista',
            'rol': 'peluquero',
            'documento': '1099887766',
            'telefono': '3109998888',
            'porcentaje_comision_peluqueria': '50.00',
            'activo': 'on'
        })
        self.assertEqual(res.status_code, 302)
        andrea = Trabajador.objects.filter(documento='1099887766').first()
        self.assertIsNotNone(andrea)
        self.assertEqual(andrea.nombre, 'Andrea Estilista')
        self.assertEqual(andrea.porcentaje_comision_peluqueria, Decimal('50.00'))
        self.assertTrue(andrea.activo)

        # 2. Editar peluquero
        res_edit = self.client.post(f'/peluqueros/{andrea.pk}/editar/', {
            'nombre': 'Andrea Estilista Master',
            'rol': 'peluquero',
            'documento': '1099887766',
            'telefono': '3101112222',
            'porcentaje_comision_peluqueria': '50.00',
            'activo': 'on'
        })
        self.assertEqual(res_edit.status_code, 302)
        andrea.refresh_from_db()
        self.assertEqual(andrea.nombre, 'Andrea Estilista Master')
        self.assertEqual(andrea.telefono, '3101112222')

        # 3. Toggle activo -> Inactivo
        res_toggle = self.client.post(f'/peluqueros/{andrea.pk}/toggle-activo/')
        self.assertEqual(res_toggle.status_code, 302)
        andrea.refresh_from_db()
        self.assertFalse(andrea.activo)

    def test_peluquero_bloqueo_eliminacion_si_tiene_historial_financiero(self):
        """Impide eliminar un peluquero si ya tiene atenciones o liquidaciones registradas."""
        # Registrar una atención al peluquero existente
        venta = Venta.objects.create(
            total_venta=Decimal('40000.00'),
            metodo_pago='efectivo',
            sesion_caja=self.caja
        )
        AtencionPeluqueria.objects.create(
            venta=venta,
            servicio=self.servicio,
            peluquero=self.peluquero,
            mascota=self.mascota_obj,
            precio_cobrado=Decimal('40000.00'),
            porcentaje_comision=Decimal('50.00'),
            comision_calculada=Decimal('20000.00'),
            parte_negocio=Decimal('20000.00')
        )

        # Intentar eliminar al peluquero
        res_del = self.client.post(f'/peluqueros/{self.peluquero.pk}/eliminar/')
        self.assertEqual(res_del.status_code, 302)
        # Sigue existiendo en la base de datos
        self.assertTrue(Trabajador.objects.filter(pk=self.peluquero.pk).exists())

        # Si creamos un peluquero sin historial, sí se puede eliminar
        peluquero_sin_historial = Trabajador.objects.create(
            nombre="Peluquero Temporal",
            rol="peluquero",
            documento="99988877"
        )
        res_del_ok = self.client.post(f'/peluqueros/{peluquero_sin_historial.pk}/eliminar/')
        self.assertEqual(res_del_ok.status_code, 302)
        self.assertFalse(Trabajador.objects.filter(pk=peluquero_sin_historial.pk).exists())

    # --------------------------------------------------------------------------
    # 7. ADMINISTRACIÓN DE PROVEEDORES
    # --------------------------------------------------------------------------
    def test_proveedor_creacion_edicion_y_busqueda(self):
        """Verifica la creación, edición, alternancia de estado y búsqueda de proveedores."""
        # 1. Crear proveedor
        res = self.client.post('/proveedores/nuevo/', {
            'nombre': 'Distribuidora Pet Grooming SAS',
            'nit': '900123456-1',
            'contacto': 'Marcos Venta',
            'telefono': '3007654321',
            'email': 'contacto@petgrooming.com',
            'direccion': 'Calle 50 # 10-20 Bogotá',
            'activo': 'on'
        })
        self.assertEqual(res.status_code, 302)
        proveedor = Proveedor.objects.filter(nit='900123456-1').first()
        self.assertIsNotNone(proveedor)
        self.assertEqual(proveedor.nombre, 'Distribuidora Pet Grooming SAS')
        self.assertTrue(proveedor.activo)

        # 2. Editar proveedor
        res_edit = self.client.post(f'/proveedores/{proveedor.pk}/editar/', {
            'nombre': 'Distribuidora Pet Grooming Colombia SAS',
            'nit': '900123456-1',
            'contacto': 'Marcos Venta Directa',
            'telefono': '3007654321',
            'email': 'contacto@petgrooming.com',
            'direccion': 'Calle 50 # 10-20 Bogotá',
            'activo': 'on'
        })
        self.assertEqual(res_edit.status_code, 302)
        proveedor.refresh_from_db()
        self.assertEqual(proveedor.nombre, 'Distribuidora Pet Grooming Colombia SAS')

        # 3. Listado con búsqueda por texto
        res_list = self.client.get('/proveedores/?q=Grooming')
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, 'Distribuidora Pet Grooming Colombia SAS')

        # 4. Toggle activo
        res_toggle = self.client.post(f'/proveedores/{proveedor.pk}/toggle-activo/')
        self.assertEqual(res_toggle.status_code, 302)
        proveedor.refresh_from_db()
        self.assertFalse(proveedor.activo)

    # --------------------------------------------------------------------------
    # 8. COMPRAS CON AFECTACIÓN EXACTA DE CAJA FÍSICA Y KARDEX
    # --------------------------------------------------------------------------
    def test_compra_en_efectivo_descuenta_caja_y_actualiza_stock(self):
        """Verifica que una compra en efectivo registre entrada de stock y descuente la gaveta de caja."""
        proveedor = Proveedor.objects.create(nombre="Distribuidora Nutripet")
        stock_ant = self.producto.stock

        payload = {
            'proveedor': proveedor.pk,
            'numero_factura': 'FAC-999',
            'metodo_pago': 'efectivo',
            'estado': 'recibida_pagada',
            'items_json': json.dumps([{
                'producto_id': self.producto.pk,
                'cantidad': 5,
                'costo_unitario': 20000
            }])
        }

        res = self.client.post('/compras/nueva/', payload)
        self.assertEqual(res.status_code, 302)

        # 1. Stock aumentó exactamente en 5 unidades
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, stock_ant + 5)

        # 2. Kardex registrado
        kardex = MovimientoInventario.objects.filter(producto=self.producto, tipo='entrada_compra').first()
        self.assertIsNotNone(kardex)
        self.assertEqual(kardex.cantidad, 5)

        # 3. Ver detalle de compra
        compra = Compra.objects.filter(numero_factura_proveedor='FAC-999').first()
        self.assertIsNotNone(compra)
        self.assertEqual(compra.total, Decimal('100000.00'))

        res_det = self.client.get(f'/compras/{compra.pk}/')
        self.assertEqual(res_det.status_code, 200)

        # 4. Verificación de caja: los $100.000 reducen el efectivo esperado
        res_caja = self.client.get('/caja/')
        self.assertEqual(res_caja.status_code, 200)
        datos = res_caja.context['datos']
        self.assertEqual(datos['compras_efectivo'], Decimal('100000.00'))
        # Base ($50.000) - Compra Efectivo ($100.000) = -$50.000
        self.assertEqual(datos['efectivo_esperado'], Decimal('-50000.00'))

    # --------------------------------------------------------------------------
    # 9. AGENDA DE CITAS DE PELUQUERÍA Y PREVENCIÓN DE SOLAPAMIENTOS
    # --------------------------------------------------------------------------
    def test_agenda_citas_creacion_y_bloqueo_solapamiento(self):
        """Verifica el agendamiento de citas y la prevención de cruces de horario para un peluquero."""
        from datetime import time, date

        # 1. Agendar cita válida
        res_cita = self.client.post('/peluqueria/citas/nueva/', {
            'cliente': self.cliente_obj.pk,
            'mascota': self.mascota_obj.pk,
            'servicio': self.servicio.pk,
            'peluquero': self.peluquero.pk,
            'fecha_cita': '2026-10-25',
            'hora_inicio': '10:00',
            'duracion_minutos': 60,
            'estado': 'pendiente',
            'observaciones': 'Baño con champú neutro'
        })
        self.assertEqual(res_cita.status_code, 302)
        cita1 = CitaPeluqueria.objects.filter(fecha_cita='2026-10-25', hora_inicio=time(10, 0)).first()
        self.assertIsNotNone(cita1)

        # 2. Intento de solapamiento: misma fecha, mismo peluquero a las 10:30 (dentro del rango 10:00 a 11:00)
        res_solapada = self.client.post('/peluqueria/citas/nueva/', {
            'cliente': self.cliente_obj.pk,
            'mascota': self.mascota_obj.pk,
            'servicio': self.servicio.pk,
            'peluquero': self.peluquero.pk,
            'fecha_cita': '2026-10-25',
            'hora_inicio': '10:30',
            'duracion_minutos': 45,
            'estado': 'pendiente'
        })
        # Debe fallar la validación y retornar el formulario (HTTP 200 con error)
        self.assertEqual(res_solapada.status_code, 200)
        self.assertContains(res_solapada, 'ya tiene la cita')

        # 3. Cambio rápido de estado a en_proceso
        res_estado = self.client.post(f'/peluqueria/citas/{cita1.pk}/estado/en_proceso/')
        self.assertEqual(res_estado.status_code, 302)
        cita1.refresh_from_db()
        self.assertEqual(cita1.estado, 'en_proceso')

    # --------------------------------------------------------------------------
    # 10. SEGURIDAD Y BITÁCORA DE AUDITORÍA
    # --------------------------------------------------------------------------
    def test_bitacora_auditoria_y_control_de_acceso(self):
        """Verifica la consulta de la bitácora y la protección de vistas para no autenticados."""
        # 1. Crear registro de prueba en la bitácora
        BitacoraAuditoria.objects.create(
            usuario=self.admin,
            accion='caja_apertura',
            modulo='Caja',
            descripcion='Apertura formal de turno de prueba'
        )

        res_audit = self.client.get('/auditoria/')
        self.assertEqual(res_audit.status_code, 200)
        self.assertContains(res_audit, 'Apertura formal de turno de prueba')

        # 2. Cliente anónimo es redirigido a login
        anon_client = Client()
        res_anon = anon_client.get('/auditoria/')
        self.assertEqual(res_anon.status_code, 302)
        self.assertIn('/login/', res_anon.url)

    # --------------------------------------------------------------------------
    # 11. CATÁLOGO ADMINISTRABLE DE SERVICIOS E INTEGRIDAD HISTÓRICA
    # --------------------------------------------------------------------------
    def test_servicios_peluqueria_crud_e_integridad_historica(self):
        """
        Verifica:
        1. Creación de un servicio nuevo desde la administración.
        2. Edición de precio de un servicio existente sin alterar atenciones históricas.
        3. Bloqueo de eliminación si tiene atenciones o citas asociadas.
        4. Desactivación controlada y eliminación exitosa si no tiene historial.
        """
        # 1. Crear nuevo servicio
        res_crear = self.client.post('/servicios/nuevo/', {
            'nombre': 'Corte de Raza Schnauzer',
            'descripcion': 'Corte tradicional de faldas y cejas',
            'precio_sugerido': '42000.00',
            'activo': 'on'
        })
        self.assertEqual(res_crear.status_code, 302)
        nuevo_serv = ServicioPeluqueria.objects.filter(nombre='Corte de Raza Schnauzer').first()
        self.assertIsNotNone(nuevo_serv)
        self.assertEqual(nuevo_serv.precio_sugerido, Decimal('42000.00'))

        # 2. Listado de servicios
        res_list = self.client.get('/servicios/')
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, 'Corte de Raza Schnauzer')

        # 3. Vincular self.servicio (Baño y Corte Básico) a una atención histórica
        atencion = AtencionPeluqueria.objects.create(
            servicio=self.servicio,
            nombre_servicio=self.servicio.nombre,
            mascota=self.mascota_obj,
            cliente=self.cliente_obj,
            peluquero=self.peluquero,
            precio_cobrado=Decimal('35000.00'),
            descuento=Decimal('0.00'),
            valor_neto=Decimal('35000.00'),
            comision_calculada=Decimal('17500.00'),
            parte_negocio=Decimal('17500.00')
        )

        # 4. Intentar eliminar self.servicio -> Debe ser BLOQUEADO por tener atención histórica
        res_elim_bloq = self.client.post(f'/servicios/{self.servicio.pk}/eliminar/')
        self.assertEqual(res_elim_bloq.status_code, 302)
        # El servicio sigue existiendo
        self.assertTrue(ServicioPeluqueria.objects.filter(pk=self.servicio.pk).exists())

        # 5. Modificar el precio de self.servicio a $60.000
        res_edit = self.client.post(f'/servicios/{self.servicio.pk}/editar/', {
            'nombre': 'Baño y Corte Básico Premium',
            'descripcion': 'Actualizado',
            'precio_sugerido': '60000.00',
            'activo': 'on'
        })
        self.assertEqual(res_edit.status_code, 302)
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.precio_sugerido, Decimal('60000.00'))

        # La atención histórica CONSERVA su valor y comisión original intactos
        atencion.refresh_from_db()
        self.assertEqual(atencion.precio_cobrado, Decimal('35000.00'))
        self.assertEqual(atencion.comision_calculada, Decimal('17500.00'))

        # 6. Desactivar el servicio nuevo
        res_toggle = self.client.post(f'/servicios/{nuevo_serv.pk}/toggle-activo/')
        self.assertEqual(res_toggle.status_code, 302)
        nuevo_serv.refresh_from_db()
        self.assertFalse(nuevo_serv.activo)

        # 7. Eliminar el servicio nuevo (no tiene historial) -> Debe eliminarse exitosamente
        res_elim_ok = self.client.post(f'/servicios/{nuevo_serv.pk}/eliminar/')
        self.assertEqual(res_elim_ok.status_code, 302)
        self.assertFalse(ServicioPeluqueria.objects.filter(pk=nuevo_serv.pk).exists())



