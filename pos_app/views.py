"""
views.py - Vistas del sistema POS Pet Shop, Peluquería Canina y Tienda de Mascotas.
Implementación robusta con transacciones atómicas, soporte de lector de códigos de barras,
pagos mixtos, liquidación diaria de peluqueros (comisión 50%, adelantos, arrastre de saldos),
cierre de caja con separación estricta de efectivo físico y banco, y reporte de ganancias reales.
"""
import io
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    AdelantoPeluqueroForm, AperturaCajaForm, CategoriaForm,
    CierreCajaForm, ClienteForm, EgresoForm, MascotaForm,
    ProductoForm, ProveedorForm, ServicioPeluqueriaForm, TrabajadorForm
)
from .models import (
    AdelantoPeluquero, AtencionPeluqueria, Categoria, Cliente,
    Compra, DetalleCompra, DetalleVenta, Egreso,
    LiquidacionPeluquero, Mascota, MovimientoInventario, PagoLiquidacion,
    PagoVenta, Producto, Proveedor, ServicioPeluqueria,
    SesionCaja, Trabajador, Venta
)

User = get_user_model()


# ==============================================================================
# HELPERS DE CAJA ACTIVA
# ==============================================================================

def obtener_caja_activa():
    """Retorna la sesión de caja abierta actual, o None."""
    return SesionCaja.objects.filter(estado='abierta').order_by('-fecha_apertura').first()


# ==============================================================================
# DASHBOARD PRINCIPAL
# ==============================================================================

@login_required
def dashboard(request):
    """
    Panel de control ejecutivo con indicadores reales del Pet Shop & Peluquería.
    Distingue: ingresos productos vs peluquería, comisiones generadas, adelantos,
    pagos al personal, gastos operativos, saldo de caja y ganancia económica estimada.
    """
    now = timezone.localtime()
    hoy = now.date()

    inicio_dia = timezone.make_aware(datetime.combine(hoy, datetime.min.time()))
    fin_dia = timezone.make_aware(datetime.combine(hoy, datetime.max.time()))

    inicio_mes = hoy.replace(day=1)
    inicio_mes_dt = timezone.make_aware(datetime.combine(inicio_mes, datetime.min.time()))

    # Ventas del día (no anuladas)
    ventas_hoy = Venta.objects.filter(fecha__gte=inicio_dia, fecha__lte=fin_dia, estado='completada')
    total_ventas_hoy = ventas_hoy.aggregate(t=Sum('total_venta'))['t'] or Decimal('0.00')
    
    # Desglose de ingresos de hoy
    ingresos_productos_hoy = DetalleVenta.objects.filter(
        venta__in=ventas_hoy
    ).aggregate(t=Sum('subtotal'))['t'] or Decimal('0.00')

    costo_productos_hoy = DetalleVenta.objects.filter(
        venta__in=ventas_hoy
    ).aggregate(t=Sum(F('precio_compra') * F('cantidad')))['t'] or Decimal('0.00')

    ganancia_productos_hoy = ingresos_productos_hoy - costo_productos_hoy

    # Servicios de peluquería hoy
    atenciones_hoy = AtencionPeluqueria.objects.filter(
        fecha__gte=inicio_dia, fecha__lte=fin_dia
    ).exclude(estado_liquidacion='anulado')
    
    total_servicios_hoy = atenciones_hoy.aggregate(t=Sum('valor_neto'))['t'] or Decimal('0.00')
    comisiones_peluquero_hoy = atenciones_hoy.aggregate(t=Sum('comision_calculada'))['t'] or Decimal('0.00')
    parte_negocio_peluqueria_hoy = total_servicios_hoy - comisiones_peluquero_hoy
    cantidad_servicios_hoy = atenciones_hoy.count()

    # Egresos y gastos operativos del día
    egresos_hoy_qs = Egreso.objects.filter(fecha__gte=inicio_dia, fecha__lte=fin_dia)
    gastos_operativos_hoy = egresos_hoy_qs.exclude(categoria='personal').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
    pagos_personal_hoy = egresos_hoy_qs.filter(categoria='personal').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
    total_egresos_hoy = gastos_operativos_hoy + pagos_personal_hoy

    # Adelantos y pagos a peluqueros de hoy
    adelantos_peluquero_hoy = AdelantoPeluquero.objects.filter(
        fecha__gte=inicio_dia, fecha__lte=fin_dia
    ).exclude(estado='anulado').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

    pagos_liquidacion_hoy = PagoLiquidacion.objects.filter(
        fecha__gte=inicio_dia, fecha__lte=fin_dia, estado='confirmado'
    ).aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

    # Ganancia estimada del día:
    # Ganancia bruta productos + Parte neta de peluquería - Gastos operativos generales
    ganancia_estimada_hoy = ganancia_productos_hoy + parte_negocio_peluqueria_hoy - gastos_operativos_hoy - pagos_personal_hoy

    # Estado de caja activa
    caja_activa = obtener_caja_activa()
    efectivo_en_caja = Decimal('0.00')
    banco_dia = Decimal('0.00')

    if caja_activa:
        # Calcular efectivo físico y banco de la sesión actual
        pagos_caja = PagoVenta.objects.filter(venta__sesion_caja=caja_activa, venta__estado='completada')
        efectivo_ingresos = pagos_caja.filter(metodo='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        banco_ingresos = pagos_caja.exclude(metodo='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

        egresos_efectivo = Egreso.objects.filter(sesion_caja=caja_activa, metodo_pago='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        adelantos_efectivo = AdelantoPeluquero.objects.filter(sesion_caja=caja_activa, medio_entrega='efectivo').exclude(estado='anulado').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        pagos_pelu_efectivo = PagoLiquidacion.objects.filter(sesion_caja=caja_activa, medio_pago='efectivo', estado='confirmado').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

        efectivo_en_caja = caja_activa.monto_inicial_efectivo + efectivo_ingresos - egresos_efectivo - adelantos_efectivo - pagos_pelu_efectivo
        banco_dia = banco_ingresos

    # Inventario
    total_productos = Producto.objects.filter(activo=True).count()
    productos_stock_bajo = Producto.objects.filter(activo=True, stock__lte=F('stock_minimo')).count()

    # Últimas ventas y atenciones
    ultimas_ventas = Venta.objects.filter(estado='completada').prefetch_related('detalles__producto', 'servicios_peluqueria', 'pagos')[:6]

    # Liquidaciones pendientes
    liquidaciones_abiertas = LiquidacionPeluquero.objects.exclude(estado='liquidada').order_by('-fecha_jornada')[:5]

    # Datos para gráfico últimos 7 días
    labels_7dias = []
    data_ventas_7dias = []
    data_servicios_7dias = []
    data_ganancia_7dias = []

    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        ini_d = timezone.make_aware(datetime.combine(dia, datetime.min.time()))
        fin_d = timezone.make_aware(datetime.combine(dia, datetime.max.time()))

        v_dia = Venta.objects.filter(fecha__gte=ini_d, fecha__lte=fin_d, estado='completada')
        tot_v = v_dia.aggregate(t=Sum('total_venta'))['t'] or Decimal('0.00')
        
        serv_dia = AtencionPeluqueria.objects.filter(fecha__gte=ini_d, fecha__lte=fin_d).exclude(estado_liquidacion='anulado')
        tot_serv = serv_dia.aggregate(t=Sum('valor_neto'))['t'] or Decimal('0.00')

        labels_7dias.append(dia.strftime('%d/%m'))
        data_ventas_7dias.append(float(tot_v))
        data_servicios_7dias.append(float(tot_serv))

    context = {
        'total_ventas_hoy': total_ventas_hoy,
        'num_ventas_hoy': ventas_hoy.count(),
        'ingresos_productos_hoy': ingresos_productos_hoy,
        'ganancia_productos_hoy': ganancia_productos_hoy,
        'total_servicios_hoy': total_servicios_hoy,
        'cantidad_servicios_hoy': cantidad_servicios_hoy,
        'comisiones_peluquero_hoy': comisiones_peluquero_hoy,
        'parte_negocio_peluqueria_hoy': parte_negocio_peluqueria_hoy,
        'total_egresos_hoy': total_egresos_hoy,
        'pagos_personal_hoy': pagos_personal_hoy,
        'adelantos_peluquero_hoy': adelantos_peluquero_hoy,
        'pagos_liquidacion_hoy': pagos_liquidacion_hoy,
        'ganancia_estimada_hoy': ganancia_estimada_hoy,
        'caja_activa': caja_activa,
        'efectivo_en_caja': efectivo_en_caja,
        'banco_dia': banco_dia,
        'total_productos': total_productos,
        'productos_stock_bajo': productos_stock_bajo,
        'ultimas_ventas': ultimas_ventas,
        'liquidaciones_abiertas': liquidaciones_abiertas,
        'labels_7dias': json.dumps(labels_7dias),
        'data_ventas_7dias': json.dumps(data_ventas_7dias),
        'data_servicios_7dias': json.dumps(data_servicios_7dias),
    }
    return render(request, 'dashboard/dashboard.html', context)


# ==============================================================================
# PUNTO DE VENTA (POS) - PRODUCTOS + SERVICIOS + SCANNER + PAGOS MIXTOS
# ==============================================================================

@login_required
def pos(request):
    """
    Pantalla principal de POS adaptada:
    - Escaneo con lector de código de barras USB (actúa como teclado).
    - Venta de productos físicos con validación estricta de stock.
    - Venta de servicios de peluquería con selección de mascota/cliente y peluquero asignado.
    - Soporte de pagos mixtos (Efectivo + Transferencia/Tarjeta).
    """
    productos = Producto.objects.filter(activo=True).select_related('categoria')
    categorias = Categoria.objects.all()
    servicios = ServicioPeluqueria.objects.filter(activo=True)
    peluqueros = Trabajador.objects.filter(activo=True, rol='peluquero')
    clientes = Cliente.objects.all().prefetch_related('mascotas')
    caja_activa = obtener_caja_activa()

    context = {
        'productos': productos,
        'categorias': categorias,
        'servicios': servicios,
        'peluqueros': peluqueros,
        'clientes': clientes,
        'caja_activa': caja_activa,
    }
    return render(request, 'sales/pos.html', context)


@login_required
@require_GET
def api_buscar_producto(request):
    """API para búsqueda manual y por lector de código de barras."""
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '').strip()
    barcode = request.GET.get('barcode', '').strip()

    productos = Producto.objects.filter(activo=True)

    if barcode:
        # Búsqueda exacta por código de barras / sku
        productos = productos.filter(Q(sku__iexact=barcode) | Q(codigo_interno__iexact=barcode))
    elif q:
        productos = productos.filter(
            Q(nombre__icontains=q) | Q(sku__icontains=q) | Q(codigo_interno__icontains=q)
        )
    if cat:
        productos = productos.filter(categoria_id=cat)

    data = [
        {
            'id': p.pk,
            'nombre': p.nombre,
            'sku': p.sku,
            'codigo_interno': p.codigo_interno or '',
            'precio_venta': float(p.precio_venta),
            'precio_compra': float(p.precio_compra),
            'stock': p.stock,
            'unidad': p.get_unidad_medida_display(),
            'categoria': p.categoria.nombre if p.categoria else 'General',
        }
        for p in productos[:50]
    ]
    return JsonResponse({'productos': data})


@login_required
@require_POST
def procesar_venta(request):
    """
    Procesamiento transaccional de una venta combinada (productos y/o servicios de peluquería).
    Garantiza:
    1. Idempotencia y prevención de doble clic.
    2. Bloqueo pesimista (select_for_update) sobre existencias de inventario.
    3. Validación y desglose estricto de medios de pago (efectivo, transferencia, mixto).
    4. Cálculo de comisión del 50% al peluquero SOLO en servicios de peluquería.
    5. Kardex de movimientos de inventario y asociación a caja activa.
    """
    try:
        data = json.loads(request.body)
        items_productos = data.get('productos', [])
        items_servicios = data.get('servicios', [])
        metodo_pago = data.get('metodo_pago', 'efectivo')
        pagos_desglose = data.get('pagos', [])  # [{'metodo': 'efectivo', 'monto': 20000}, ...]
        cliente_id = data.get('cliente_id')
        notas = data.get('notas', '')
        uuid_op = data.get('uuid_operacion') or str(uuid.uuid4())

        if not items_productos and not items_servicios:
            return JsonResponse({'success': False, 'error': 'El carrito está vacío. Agregue productos o servicios.'})

        caja_activa = obtener_caja_activa()

        with transaction.atomic():
            # Idempotencia: evitar duplicados
            if Venta.objects.filter(uuid_operacion=uuid_op).exists():
                venta_existente = Venta.objects.get(uuid_operacion=uuid_op)
                return JsonResponse({
                    'success': True,
                    'venta_id': venta_existente.pk,
                    'total': float(venta_existente.total_venta),
                    'mensaje': 'Venta ya procesada previamente (evitada duplicación).'
                })

            cliente = None
            if cliente_id:
                cliente = Cliente.objects.filter(pk=cliente_id).first()

            # 1. Crear venta preliminar
            venta = Venta.objects.create(
                cliente=cliente,
                sesion_caja=caja_activa,
                metodo_pago=metodo_pago,
                notas=notas,
                uuid_operacion=uuid_op,
            )

            total_productos = Decimal('0.00')
            total_costo_productos = Decimal('0.00')
            total_servicios = Decimal('0.00')
            total_comision_peluquero = Decimal('0.00')

            # 2. Procesar productos físicos (con control estricto de concurrencia y stock)
            for item in items_productos:
                prod_id = item['producto_id']
                cantidad = int(item['cantidad'])
                precio_unitario = Decimal(str(item['precio_venta']))

                if cantidad <= 0:
                    raise ValueError("La cantidad de productos debe ser mayor a cero.")

                # Bloqueo para evitar inconsistencias concurrentes
                producto = Producto.objects.select_for_update().get(pk=prod_id)

                if producto.stock < cantidad:
                    raise ValueError(f"Stock insuficiente para '{producto.nombre}'. Disponible: {producto.stock}, solicitado: {cantidad}.")

                subtotal = precio_unitario * cantidad
                costo_total = producto.precio_compra * cantidad

                DetalleVenta.objects.create(
                    venta=venta,
                    producto=producto,
                    nombre_producto=producto.nombre,
                    sku_producto=producto.sku,
                    cantidad=cantidad,
                    precio_venta=precio_unitario,
                    precio_compra=producto.precio_compra,
                    subtotal=subtotal
                )

                # Descontar stock y registrar Kardex
                stock_ant = producto.stock
                producto.stock -= cantidad
                producto.save()

                MovimientoInventario.objects.create(
                    producto=producto,
                    tipo='salida_venta',
                    cantidad=cantidad,
                    stock_anterior=stock_ant,
                    stock_nuevo=producto.stock,
                    motivo=f'Venta #{venta.pk}',
                    referencia_origen=f'Venta #{venta.pk}',
                    usuario=request.user
                )

                total_productos += subtotal
                total_costo_productos += costo_total

            # 3. Procesar servicios de peluquería
            for srv_item in items_servicios:
                servicio_id = srv_item['servicio_id']
                peluquero_id = srv_item['peluquero_id']
                mascota_id = srv_item.get('mascota_id')
                precio_cobrado = Decimal(str(srv_item['precio']))
                descuento = Decimal(str(srv_item.get('descuento', 0)))

                servicio = ServicioPeluqueria.objects.get(pk=servicio_id)
                peluquero = Trabajador.objects.get(pk=peluquero_id)
                mascota = Mascota.objects.filter(pk=mascota_id).first() if mascota_id else None

                atencion = AtencionPeluqueria.objects.create(
                    venta=venta,
                    servicio=servicio,
                    nombre_servicio=servicio.nombre,
                    mascota=mascota,
                    cliente=cliente or (mascota.cliente if mascota else None),
                    peluquero=peluquero,
                    precio_cobrado=precio_cobrado,
                    descuento=descuento,
                    porcentaje_comision=peluquero.porcentaje_comision_peluqueria,
                    observaciones=srv_item.get('observaciones', '')
                )

                total_servicios += atencion.valor_neto
                total_comision_peluquero += atencion.comision_calculada

            # 4. Totales globales
            total_general = total_productos + total_servicios
            ganancia_productos = total_productos - total_costo_productos
            ganancia_servicios = total_servicios - total_comision_peluquero
            ganancia_neta_total = ganancia_productos + ganancia_servicios

            venta.subtotal = total_general
            venta.total_venta = total_general
            venta.total_costo_productos = total_costo_productos
            venta.total_ganancia_productos = ganancia_productos
            venta.total_servicios = total_servicios
            venta.total_comision_peluquero = total_comision_peluquero
            venta.total_ganancia = ganancia_neta_total
            venta.save()

            # 5. Registrar desglose de medios de pago
            total_pagos_recibidos = Decimal('0.00')

            if pagos_desglose:
                for p in pagos_desglose:
                    monto_pago = Decimal(str(p['monto']))
                    if monto_pago > Decimal('0.00'):
                        PagoVenta.objects.create(
                            venta=venta,
                            metodo=p['metodo'],
                            monto=monto_pago,
                            referencia=p.get('referencia', '')
                        )
                        total_pagos_recibidos += monto_pago
                
                # Validación estricta: suma de pagos = total de la venta
                if abs(total_pagos_recibidos - total_general) > Decimal('0.01'):
                    raise ValueError(f"La suma de los pagos (${total_pagos_recibidos:,.2f}) no coincide exactamente con el total de la venta (${total_general:,.2f}).")
            else:
                # Si no se envió desglose múltiple, usar método principal directo
                PagoVenta.objects.create(
                    venta=venta,
                    metodo=metodo_pago,
                    monto=total_general
                )

        return JsonResponse({
            'success': True,
            'venta_id': venta.pk,
            'total': float(total_general),
            'ganancia': float(ganancia_neta_total),
            'mensaje': f'Venta #{venta.pk} registrada con éxito.'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def venta_detalle(request, pk):
    """Detalle completo e imprimible de la venta."""
    venta = get_object_or_404(Venta, pk=pk)
    detalles = venta.detalles.select_related('producto').all()
    servicios = venta.servicios_peluqueria.select_related('servicio', 'peluquero', 'mascota').all()
    pagos = venta.pagos.all()

    return render(request, 'sales/venta_detalle.html', {
        'venta': venta,
        'detalles': detalles,
        'servicios': servicios,
        'pagos': pagos,
    })


@login_required
def historial_ventas(request):
    """Historial con filtros avanzados, búsqueda y estados."""
    ventas = Venta.objects.select_related('cliente', 'sesion_caja').prefetch_related('detalles', 'servicios_peluqueria', 'pagos')

    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    metodo = request.GET.get('metodo', '')
    estado = request.GET.get('estado', '')

    if fecha_desde:
        ventas = ventas.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        ventas = ventas.filter(fecha__date__lte=fecha_hasta)
    if metodo:
        ventas = ventas.filter(metodo_pago=metodo)
    if estado:
        ventas = ventas.filter(estado=estado)

    totales = ventas.filter(estado='completada').aggregate(
        total=Sum('total_venta'),
        ganancia=Sum('total_ganancia'),
        num=Count('id')
    )

    paginator = Paginator(ventas, 25)
    page = request.GET.get('page', 1)
    ventas_paginadas = paginator.get_page(page)

    return render(request, 'sales/historial.html', {
        'ventas': ventas_paginadas,
        'totales': totales,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'metodo': metodo,
        'estado': estado,
    })


@login_required
@require_POST
def anular_venta(request, pk):
    """
    Anulación segura y trazable de una venta:
    - Retorna stock al inventario mediante movimiento compensatorio.
    - Anula atenciones de peluquería asociadas (revisando si ya fueron liquidadas).
    - Preserva registro histórico con motivo.
    """
    venta = get_object_or_404(Venta, pk=pk)
    motivo = request.POST.get('motivo', 'Anulación solicitada por el administrador')

    if venta.estado == 'anulada':
        messages.warning(request, "Esta venta ya fue anulada previamente.")
        return redirect('venta_detalle', pk=pk)

    # Verificar si algún servicio de peluquería ya fue liquidado en jornada cerrada
    for serv in venta.servicios_peluqueria.all():
        if serv.estado_liquidacion == 'liquidado':
            messages.error(
                request,
                f"No se puede anular la venta directamente porque el servicio de peluquería '{serv.nombre_servicio}' ya fue liquidado al trabajador. Se debe gestionar un ajuste contable."
            )
            return redirect('venta_detalle', pk=pk)

    with transaction.atomic():
        venta.estado = 'anulada'
        venta.motivo_anulacion = motivo
        venta.anulada_en = timezone.now()
        venta.save()

        # Reintegrar productos a inventario
        for det in venta.detalles.all():
            prod = det.producto
            stock_ant = prod.stock
            prod.stock += det.cantidad
            prod.save()

            MovimientoInventario.objects.create(
                producto=prod,
                tipo='anulacion_venta',
                cantidad=det.cantidad,
                stock_anterior=stock_ant,
                stock_nuevo=prod.stock,
                motivo=f'Devolución por anulación de Venta #{venta.pk}: {motivo}',
                referencia_origen=f'Venta #{venta.pk}',
                usuario=request.user
            )

        # Anular comisiones de peluquería
        for serv in venta.servicios_peluqueria.all():
            serv.estado_liquidacion = 'anulado'
            serv.observaciones = f"Anulado por venta #{venta.pk}: {motivo}"
            serv.save()

    messages.success(request, f"Venta #{venta.pk} anulada exitosamente y stock reintegrado.")
    return redirect('venta_detalle', pk=pk)


# ==============================================================================
# MÓDULO ESPECIAL: PELUQUERÍA, COMISIONES, ADELANTOS Y LIQUIDACIÓN DIARIA
# ==============================================================================

@login_required
def peluqueria_dashboard(request):
    """
    Panel central del módulo de peluquería canina:
    - Atenciones de la jornada y comisiones generadas (50%).
    - Adelantos entregados.
    - Cierres y liquidaciones por peluquero.
    """
    hoy = timezone.now().date()
    peluqueros = Trabajador.objects.filter(activo=True, rol='peluquero')
    servicios_catalogo = ServicioPeluqueria.objects.all()

    # Atenciones del día
    atenciones_hoy = AtencionPeluqueria.objects.filter(fecha__date=hoy).select_related('peluquero', 'servicio', 'mascota')
    adelantos_hoy = AdelantoPeluquero.objects.filter(fecha__date=hoy).select_related('peluquero')
    liquidaciones_recientes = LiquidacionPeluquero.objects.all().select_related('peluquero')[:10]

    context = {
        'hoy': hoy,
        'peluqueros': peluqueros,
        'servicios_catalogo': servicios_catalogo,
        'atenciones_hoy': atenciones_hoy,
        'adelantos_hoy': adelantos_hoy,
        'liquidaciones_recientes': liquidaciones_recientes,
    }
    return render(request, 'peluqueria/dashboard.html', context)


@login_required
def adelanto_registrar(request):
    """Registra un adelanto de dinero al peluquero y afecta caja o banco."""
    caja_activa = obtener_caja_activa()
    if request.method == 'POST':
        form = AdelantoPeluqueroForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                adelanto = form.save(commit=False)
                adelanto.sesion_caja = caja_activa
                adelanto.save()
            messages.success(request, f"Adelanto de ${adelanto.monto:,.0f} registrado para {adelanto.peluquero.nombre}.")
            return redirect('peluqueria_dashboard')
    else:
        form = AdelantoPeluqueroForm()

    return render(request, 'peluqueria/adelanto_form.html', {'form': form, 'caja_activa': caja_activa})


@login_required
def liquidacion_jornada(request, peluquero_id):
    """
    Pantalla interactiva de liquidación diaria para un peluquero:
    Formula:
    Saldo por pagar = Saldo anterior + Comisiones jornada - Adelantos jornada - Pagos.
    Permite arrastre automático de saldos pendientes de jornadas anteriores.
    """
    peluquero = get_object_or_404(Trabajador, pk=peluquero_id)
    hoy = timezone.now().date()
    caja_activa = obtener_caja_activa()

    # Buscar liquidación del día o servicios pendientes de liquidar
    servicios_pendientes = AtencionPeluqueria.objects.filter(
        peluquero=peluquero,
        estado_liquidacion='pendiente'
    ).select_related('servicio', 'mascota')

    adelantos_pendientes = AdelantoPeluquero.objects.filter(
        peluquero=peluquero,
        estado='pendiente'
    )

    # Arrastre de saldo anterior: buscar la última liquidación cerrada con saldo pendiente
    ultima_liq = LiquidacionPeluquero.objects.filter(
        peluquero=peluquero
    ).exclude(estado='liquidada').exclude(estado='anulada').first()

    saldo_anterior = Decimal('0.00')
    if ultima_liq and ultima_liq.fecha_jornada < hoy:
        saldo_anterior = ultima_liq.saldo_pendiente

    total_comision_servicios = sum((s.comision_calculada for s in servicios_pendientes), Decimal('0.00'))
    total_adelantos = sum((a.monto for a in adelantos_pendientes), Decimal('0.00'))
    saldo_a_liquidar = saldo_anterior + total_comision_servicios - total_adelantos

    if request.method == 'POST':
        accion = request.POST.get('accion')
        monto_pago = Decimal(request.POST.get('monto_pago', '0'))
        medio_pago = request.POST.get('medio_pago', 'efectivo')
        observacion = request.POST.get('observacion', '')

        with transaction.atomic():
            # Crear o actualizar liquidación de hoy
            liq, created = LiquidacionPeluquero.objects.get_or_create(
                peluquero=peluquero,
                fecha_jornada=hoy,
                defaults={
                    'saldo_anterior': saldo_anterior,
                    'observaciones': observacion
                }
            )

            # Imputar servicios pendientes a esta liquidación
            for serv in servicios_pendientes:
                serv.estado_liquidacion = 'liquidado'
                serv.liquidada_en = liq
                serv.save()

            # Imputar adelantos pendientes a esta liquidación
            for ad in adelantos_pendientes:
                ad.estado = 'imputado'
                ad.liquidada_en = liq
                ad.save()

            # Registrar pago si se entregó dinero en el cierre
            if monto_pago > Decimal('0.00'):
                PagoLiquidacion.objects.create(
                    liquidacion=liq,
                    sesion_caja=caja_activa,
                    monto=monto_pago,
                    medio_pago=medio_pago,
                    observacion=f"Pago de liquidación jornada {hoy}"
                )

            # Recalcular totales y saldo pendiente
            liq.recalcular()

        messages.success(request, f"Liquidación guardada para {peluquero.nombre}. Saldo pendiente: ${liq.saldo_pendiente:,.0f}")
        return redirect('peluqueria_dashboard')

    context = {
        'peluquero': peluquero,
        'hoy': hoy,
        'servicios_pendientes': servicios_pendientes,
        'adelantos_pendientes': adelantos_pendientes,
        'saldo_anterior': saldo_anterior,
        'total_comision_servicios': total_comision_servicios,
        'total_adelantos': total_adelantos,
        'saldo_a_liquidar': saldo_a_liquidar,
        'caja_activa': caja_activa,
    }
    return render(request, 'peluqueria/liquidacion_form.html', context)


# ==============================================================================
# MÓDULO OBLIGATORIO: CIERRE DE CAJA (EFECTIVO Y BANCO SEPARADOS)
# ==============================================================================

@login_required
def caja_detalle(request):
    """
    Control de caja activa, resumen en tiempo real de entradas/salidas,
    apertura de nueva jornada y cierre ciego con comparación exacta.
    """
    caja_activa = obtener_caja_activa()
    historial_cajas = SesionCaja.objects.filter(estado='cerrada').order_by('-fecha_apertura')[:10]

    datos_caja = None
    if caja_activa:
        # 1. Ventas por medio de pago
        pagos_ventas = PagoVenta.objects.filter(
            venta__sesion_caja=caja_activa, venta__estado='completada'
        )
        ventas_efectivo = pagos_ventas.filter(metodo='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        ventas_transferencia = pagos_ventas.filter(metodo='transferencia').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        ventas_tarjeta = pagos_ventas.filter(metodo='tarjeta').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        ventas_otros = pagos_ventas.filter(metodo='otro').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        total_ventas = ventas_efectivo + ventas_transferencia + ventas_tarjeta + ventas_otros

        # 2. Desglose productos vs peluquería en esta caja
        total_productos = DetalleVenta.objects.filter(
            venta__sesion_caja=caja_activa, venta__estado='completada'
        ).aggregate(t=Sum('subtotal'))['t'] or Decimal('0.00')

        total_peluqueria = AtencionPeluqueria.objects.filter(
            venta__sesion_caja=caja_activa
        ).exclude(estado_liquidacion='anulado').aggregate(t=Sum('valor_neto'))['t'] or Decimal('0.00')

        # 3. Egresos operativos y pagos de personal
        egresos_qs = Egreso.objects.filter(sesion_caja=caja_activa)
        egresos_efectivo = egresos_qs.filter(metodo_pago='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        egresos_banco = egresos_qs.exclude(metodo_pago='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

        # 4. Adelantos y liquidaciones del peluquero
        adelantos_efectivo = AdelantoPeluquero.objects.filter(
            sesion_caja=caja_activa, medio_entrega='efectivo'
        ).exclude(estado='anulado').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

        adelantos_banco = AdelantoPeluquero.objects.filter(
            sesion_caja=caja_activa, medio_entrega='transferencia'
        ).exclude(estado='anulado').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

        pagos_peluquero_efectivo = PagoLiquidacion.objects.filter(
            sesion_caja=caja_activa, medio_pago='efectivo', estado='confirmado'
        ).aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

        pagos_peluquero_banco = PagoLiquidacion.objects.filter(
            sesion_caja=caja_activa, medio_pago='transferencia', estado='confirmado'
        ).aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

        # 5. Efectivo esperado en gaveta:
        # Base Inicial + Ingresos Efectivo - Egresos Efectivo - Adelantos Efectivo - Pagos Peluquero Efectivo
        efectivo_esperado = (
            caja_activa.monto_inicial_efectivo
            + ventas_efectivo
            - egresos_efectivo
            - adelantos_efectivo
            - pagos_peluquero_efectivo
        )

        # 6. Banco neto esperado (Transferencias + Tarjetas - Salidas Bancarias)
        banco_ingresos = ventas_transferencia + ventas_tarjeta + ventas_otros
        banco_salidas = egresos_banco + adelantos_banco + pagos_peluquero_banco
        banco_neto = banco_ingresos - banco_salidas

        datos_caja = {
            'ventas_efectivo': ventas_efectivo,
            'ventas_transferencia': ventas_transferencia,
            'ventas_tarjeta': ventas_tarjeta,
            'ventas_otros': ventas_otros,
            'total_ventas': total_ventas,
            'total_productos': total_productos,
            'total_peluqueria': total_peluqueria,
            'egresos_efectivo': egresos_efectivo,
            'egresos_banco': egresos_banco,
            'adelantos_efectivo': adelantos_efectivo,
            'adelantos_banco': adelantos_banco,
            'pagos_peluquero_efectivo': pagos_peluquero_efectivo,
            'pagos_peluquero_banco': pagos_peluquero_banco,
            'efectivo_esperado': efectivo_esperado,
            'banco_ingresos': banco_ingresos,
            'banco_salidas': banco_salidas,
            'banco_neto': banco_neto,
        }

    form_apertura = AperturaCajaForm()
    form_cierre = CierreCajaForm()

    return render(request, 'caja/caja_control.html', {
        'caja_activa': caja_activa,
        'datos': datos_caja,
        'historial_cajas': historial_cajas,
        'form_apertura': form_apertura,
        'form_cierre': form_cierre,
    })


@login_required
@require_POST
def caja_abrir(request):
    """Apertura de turno de caja con saldo base."""
    if obtener_caja_activa():
        messages.warning(request, "Ya existe una caja abierta actualmente.")
        return redirect('caja_detalle')

    form = AperturaCajaForm(request.POST)
    if form.is_valid():
        monto_inicial = form.cleaned_data['monto_inicial']
        obs = form.cleaned_data['observaciones']

        SesionCaja.objects.create(
            monto_inicial_efectivo=monto_inicial,
            observaciones_apertura=obs,
            usuario_apertura=request.user,
            estado='abierta'
        )
        messages.success(request, f"Caja abierta exitosamente con una base de ${monto_inicial:,.0f} COP.")
    return redirect('caja_detalle')


@login_required
@require_POST
def caja_cerrar(request):
    """
    Cierre de caja comparativo:
    Compara el dinero físico contado por el administrador contra el efectivo calculado.
    Guarda diferencias (sobrante o faltante) y congela la sesión.
    """
    caja = obtener_caja_activa()
    if not caja:
        messages.error(request, "No hay ninguna caja abierta para cerrar.")
        return redirect('caja_detalle')

    form = CierreCajaForm(request.POST)
    if form.is_valid():
        efectivo_real = form.cleaned_data['efectivo_real']
        obs = form.cleaned_data['observaciones']

        with transaction.atomic():
            # Calcular cifras finales
            pagos = PagoVenta.objects.filter(venta__sesion_caja=caja, venta__estado='completada')
            v_efectivo = pagos.filter(metodo='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
            banco_tot = pagos.exclude(metodo='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

            e_efectivo = Egreso.objects.filter(sesion_caja=caja, metodo_pago='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
            ad_efectivo = AdelantoPeluquero.objects.filter(sesion_caja=caja, medio_entrega='efectivo').exclude(estado='anulado').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
            p_efectivo = PagoLiquidacion.objects.filter(sesion_caja=caja, medio_pago='efectivo', estado='confirmado').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

            efectivo_esperado = caja.monto_inicial_efectivo + v_efectivo - e_efectivo - ad_efectivo - p_efectivo
            diferencia = efectivo_real - efectivo_esperado

            caja.fecha_cierre = timezone.now()
            caja.efectivo_esperado = efectivo_esperado
            caja.efectivo_real = efectivo_real
            caja.diferencia_efectivo = diferencia
            caja.banco_esperado = banco_tot
            caja.observaciones_cierre = obs
            caja.usuario_cierre = request.user
            caja.estado = 'cerrada'
            caja.save()

        if diferencia == 0:
            messages.success(request, f"Caja cerrada perfectamente sin diferencias. Efectivo: ${efectivo_real:,.0f} | Banco: ${banco_tot:,.0f}")
        elif diferencia > 0:
            messages.warning(request, f"Caja cerrada con SOBRANTE de +${diferencia:,.0f}. Efectivo real: ${efectivo_real:,.0f}")
        else:
            messages.error(request, f"Caja cerrada con FALTANTE de ${abs(diferencia):,.0f}. Efectivo real: ${efectivo_real:,.0f}")

    return redirect('caja_detalle')


# ==============================================================================
# CLIENTES Y MASCOTAS
# ==============================================================================

@login_required
def clientes_list(request):
    """Directorio de clientes y dueños de mascotas."""
    q = request.GET.get('q', '').strip()
    clientes = Cliente.objects.all().prefetch_related('mascotas')
    if q:
        clientes = clientes.filter(
            Q(nombre__icontains=q) | Q(telefono__icontains=q) | Q(documento__icontains=q) | Q(mascotas__nombre__icontains=q)
        ).distinct()

    paginator = Paginator(clientes, 20)
    page = request.GET.get('page', 1)
    return render(request, 'clientes/clientes_list.html', {
        'clientes': paginator.get_page(page),
        'q': q
    })


@login_required
def cliente_crear(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"Cliente {cliente.nombre} registrado con éxito.")
            return redirect('cliente_detalle', pk=cliente.pk)
    else:
        form = ClienteForm()
    return render(request, 'clientes/cliente_form.html', {'form': form, 'titulo': 'Nuevo Cliente'})


@login_required
def cliente_editar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Datos del cliente actualizados.")
            return redirect('cliente_detalle', pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'clientes/cliente_form.html', {'form': form, 'titulo': f'Editar: {cliente.nombre}'})


@login_required
def cliente_detalle(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    mascotas = cliente.mascotas.all()
    servicios = AtencionPeluqueria.objects.filter(cliente=cliente).order_by('-fecha')[:10]
    compras = Venta.objects.filter(cliente=cliente, estado='completada').order_by('-fecha')[:10]

    return render(request, 'clientes/cliente_detalle.html', {
        'cliente': cliente,
        'mascotas': mascotas,
        'servicios': servicios,
        'compras': compras,
    })


@login_required
def mascota_crear(request, cliente_id=None):
    cliente = None
    if cliente_id:
        cliente = get_object_or_404(Cliente, pk=cliente_id)

    if request.method == 'POST':
        form = MascotaForm(request.POST)
        if form.is_valid():
            mascota = form.save()
            messages.success(request, f"Mascota {mascota.nombre} registrada correctamente.")
            if mascota.cliente:
                return redirect('cliente_detalle', pk=mascota.cliente.pk)
            return redirect('clientes_list')
    else:
        form = MascotaForm(initial={'cliente': cliente} if cliente else None)
    return render(request, 'clientes/mascota_form.html', {'form': form, 'cliente': cliente})


# ==============================================================================
# INVENTARIO Y PRODUCTOS
# ==============================================================================

@login_required
def inventario(request):
    """Catálogo y control de existencias con soporte de lector de barras."""
    productos = Producto.objects.select_related('categoria').all()

    q = request.GET.get('q', '').strip()
    cat = request.GET.get('categoria', '')
    filtro_stock = request.GET.get('stock', '')

    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) | Q(sku__icontains=q) | Q(codigo_interno__icontains=q)
        )
    if cat:
        productos = productos.filter(categoria_id=cat)
    if filtro_stock == 'bajo':
        productos = productos.filter(stock__lte=F('stock_minimo'))
    elif filtro_stock == 'sin':
        productos = productos.filter(stock=0)

    categorias = Categoria.objects.all()
    paginator = Paginator(productos, 25)
    page = request.GET.get('page', 1)

    return render(request, 'inventory/inventario.html', {
        'productos': paginator.get_page(page),
        'categorias': categorias,
        'q': q,
        'categoria_sel': cat,
        'filtro_stock': filtro_stock,
    })


@login_required
def producto_crear(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            prod = form.save()
            messages.success(request, f"Producto '{prod.nombre}' creado.")
            return redirect('inventario')
    else:
        form = ProductoForm()
    return render(request, 'inventory/producto_form.html', {'form': form, 'titulo': 'Nuevo Producto'})


@login_required
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, f"Producto '{producto.nombre}' actualizado.")
            return redirect('inventario')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'inventory/producto_form.html', {'form': form, 'titulo': f'Editar: {producto.nombre}'})


@login_required
def producto_detalle(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    movimientos = producto.movimientos.all()[:20]
    return render(request, 'inventory/producto_detalle.html', {
        'producto': producto,
        'movimientos': movimientos,
    })


@login_required
def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        producto.activo = False
        producto.save()
        messages.success(request, f"Producto '{producto.nombre}' desactivado.")
        return redirect('inventario')
    return render(request, 'inventory/producto_confirmar_eliminar.html', {'producto': producto})


# ==============================================================================
# COMPRAS Y PROVEEDORES
# ==============================================================================

@login_required
def compras_list(request):
    compras = Compra.objects.select_related('proveedor').all()
    return render(request, 'compras/compras_list.html', {'compras': compras})


@login_required
def compra_registrar(request):
    proveedores = Proveedor.objects.filter(activo=True)
    productos = Producto.objects.filter(activo=True)
    caja_activa = obtener_caja_activa()

    if request.method == 'POST':
        proveedor_id = request.POST.get('proveedor')
        numero_factura = request.POST.get('numero_factura')
        metodo_pago = request.POST.get('metodo_pago', 'efectivo')
        estado = request.POST.get('estado', 'recibida_pagada')
        items_json = request.POST.get('items_json')

        try:
            items = json.loads(items_json) if items_json else []
            if not items:
                messages.error(request, "Debe agregar al menos un producto a la compra.")
                return redirect('compra_registrar')

            with transaction.atomic():
                compra = Compra.objects.create(
                    proveedor_id=proveedor_id,
                    numero_factura_proveedor=numero_factura,
                    metodo_pago=metodo_pago,
                    estado=estado,
                    sesion_caja=caja_activa if (estado == 'recibida_pagada') else None
                )

                total_compra = Decimal('0.00')
                for it in items:
                    prod = Producto.objects.get(pk=it['producto_id'])
                    cant = int(it['cantidad'])
                    costo = Decimal(str(it['costo_unitario']))

                    DetalleCompra.objects.create(
                        compra=compra,
                        producto=prod,
                        cantidad=cant,
                        costo_unitario=costo,
                        subtotal=costo * cant
                    )

                    # Aumentar existencias y actualizar costo
                    stock_ant = prod.stock
                    prod.stock += cant
                    prod.precio_compra = costo
                    prod.save()

                    MovimientoInventario.objects.create(
                        producto=prod,
                        tipo='entrada_compra',
                        cantidad=cant,
                        stock_anterior=stock_ant,
                        stock_nuevo=prod.stock,
                        motivo=f'Compra #{compra.pk} a {compra.proveedor.nombre}',
                        referencia_origen=f'Compra #{compra.pk}',
                        usuario=request.user
                    )
                    total_compra += (costo * cant)

                compra.total = total_compra
                compra.save()

            messages.success(request, f"Compra #{compra.pk} por ${total_compra:,.0f} registrada con éxito.")
            return redirect('compras_list')

        except Exception as e:
            messages.error(request, f"Error al registrar compra: {str(e)}")

    return render(request, 'compras/compra_form.html', {
        'proveedores': proveedores,
        'productos': productos,
        'caja_activa': caja_activa
    })


# ==============================================================================
# EGRESOS OPERATIVOS Y PAGOS AL PERSONAL
# ==============================================================================

@login_required
def egresos_list_create(request):
    caja_activa = obtener_caja_activa()
    if request.method == 'POST':
        form = EgresoForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                egreso = form.save(commit=False)
                egreso.sesion_caja = caja_activa
                egreso.save()
            messages.success(request, f"Egreso de ${egreso.monto:,.0f} registrado.")
            return redirect('egresos_list_create')
    else:
        form = EgresoForm()

    egresos = Egreso.objects.all().select_related('trabajador_asociado', 'sesion_caja')
    total_egresos = egresos.aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

    return render(request, 'egresos/lista.html', {
        'form': form,
        'egresos': egresos[:30],
        'total_egresos': total_egresos,
        'caja_activa': caja_activa
    })


@login_required
def egresos_page(request):
    return redirect('egresos_list_create')


@login_required
def egresos_guardar(request):
    return redirect('egresos_list_create')


@login_required
def egreso_detail(request, pk):
    egreso = get_object_or_404(Egreso, pk=pk)
    if request.method == 'DELETE':
        egreso.delete()
        return JsonResponse({'message': 'Egreso eliminado'})
    return JsonResponse({
        'id': egreso.id,
        'nombre': egreso.nombre,
        'monto': float(egreso.monto),
        'categoria': egreso.get_categoria_display(),
        'beneficiario': egreso.beneficiario or '',
        'metodo': egreso.get_metodo_pago_display()
    })


@login_required
def eliminar_egresos(request):
    """Acción de mantenimiento restringida."""
    if request.user.is_superuser:
        Egreso.objects.all().delete()
        messages.success(request, "Todos los egresos han sido limpiados.")
    return redirect('dashboard')


# ==============================================================================
# REPORTES FINANCIEROS Y GANANCIAS REALES
# ==============================================================================

@login_required
def reportes(request):
    """
    Panel financiero integral y cálculo de ganancia económica real:
    - Ventas de productos vs servicios.
    - Costo de mercancía vendida (COGS real histórico).
    - Comisiones de peluquería (50%).
    - Egresos operativos y pagos de nómina.
    - Medios de pago (efectivo vs transferencias bancarias).
    """
    hoy = timezone.now().date()
    periodo = request.GET.get('periodo', 'mes')

    if periodo == 'hoy':
        inicio_date = hoy
        fin_date = hoy
    elif periodo == 'semana':
        inicio_date = hoy - timedelta(days=6)
        fin_date = hoy
    elif periodo == 'año':
        inicio_date = hoy.replace(month=1, day=1)
        fin_date = hoy
    elif periodo == 'personalizado':
        ini_str = request.GET.get('fecha_inicio', '')
        fin_str = request.GET.get('fecha_fin', '')
        try:
            inicio_date = datetime.strptime(ini_str, '%Y-%m-%d').date()
            fin_date = datetime.strptime(fin_str, '%Y-%m-%d').date()
        except ValueError:
            inicio_date = hoy.replace(day=1)
            fin_date = hoy
    else:  # mes por defecto
        inicio_date = hoy.replace(day=1)
        fin_date = hoy

    inicio_dt = timezone.make_aware(datetime.combine(inicio_date, datetime.min.time()))
    fin_dt = timezone.make_aware(datetime.combine(fin_date, datetime.max.time()))

    # 1. Ventas del período
    ventas_qs = Venta.objects.filter(fecha__gte=inicio_dt, fecha__lte=fin_dt, estado='completada')
    total_ventas = ventas_qs.aggregate(t=Sum('total_venta'))['t'] or Decimal('0.00')

    # 2. Desglose de Productos
    detalles_prod = DetalleVenta.objects.filter(venta__in=ventas_qs)
    ingresos_productos = detalles_prod.aggregate(t=Sum('subtotal'))['t'] or Decimal('0.00')
    costo_productos = detalles_prod.aggregate(t=Sum(F('precio_compra') * F('cantidad')))['t'] or Decimal('0.00')
    ganancia_productos = ingresos_productos - costo_productos

    # 3. Desglose de Peluquería
    atenciones_qs = AtencionPeluqueria.objects.filter(
        fecha__gte=inicio_dt, fecha__lte=fin_dt
    ).exclude(estado_liquidacion='anulado')
    ingresos_peluqueria = atenciones_qs.aggregate(t=Sum('valor_neto'))['t'] or Decimal('0.00')
    comisiones_peluqueria = atenciones_qs.aggregate(t=Sum('comision_calculada'))['t'] or Decimal('0.00')
    parte_negocio_peluqueria = ingresos_peluqueria - comisiones_peluqueria

    # 4. Egresos Operativos y Personal
    egresos_qs = Egreso.objects.filter(fecha__gte=inicio_dt, fecha__lte=fin_dt)
    gastos_operativos = egresos_qs.exclude(categoria='personal').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
    pagos_personal = egresos_qs.filter(categoria='personal').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
    total_gastos = gastos_operativos + pagos_personal

    # 5. Ganancia neta real estimada
    # (Ganancia bruta productos + Margen peluquería) - Gastos operativos y personal
    resultado_economico_neto = (ganancia_productos + parte_negocio_peluqueria) - total_gastos

    # 6. Medios de pago en el período
    pagos_qs = PagoVenta.objects.filter(venta__in=ventas_qs)
    total_efectivo = pagos_qs.filter(metodo='efectivo').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
    total_transferencia = pagos_qs.filter(metodo='transferencia').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
    total_tarjeta = pagos_qs.filter(metodo='tarjeta').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
    total_otros_medios = pagos_qs.filter(metodo='otro').aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

    # Top productos más vendidos
    top_productos = (
        detalles_prod.values('producto__nombre', 'sku_producto')
        .annotate(qty=Sum('cantidad'), ingresos=Sum('subtotal'))
        .order_by('-qty')[:10]
    )

    context = {
        'periodo': periodo,
        'fecha_inicio': inicio_date,
        'fecha_fin': fin_date,
        'total_ventas': total_ventas,
        'ingresos_productos': ingresos_productos,
        'costo_productos': costo_productos,
        'ganancia_productos': ganancia_productos,
        'ingresos_peluqueria': ingresos_peluqueria,
        'comisiones_peluqueria': comisiones_peluqueria,
        'parte_negocio_peluqueria': parte_negocio_peluqueria,
        'gastos_operativos': gastos_operativos,
        'pagos_personal': pagos_personal,
        'total_gastos': total_gastos,
        'resultado_economico_neto': resultado_economico_neto,
        'total_efectivo': total_efectivo,
        'total_transferencia': total_transferencia,
        'total_tarjeta': total_tarjeta,
        'total_otros_medios': total_otros_medios,
        'top_productos': top_productos,
    }
    return render(request, 'reports/reportes.html', context)


@login_required
def api_stock_bajo(request):
    """Devuelve listado de productos con stock mínimo alcanzado."""
    productos = Producto.objects.filter(activo=True, stock__lte=F('stock_minimo')).values(
        'id', 'nombre', 'sku', 'stock', 'stock_minimo'
    )
    return JsonResponse({'productos': list(productos)})


@login_required
def reporte_diario_pdf(request):
    """Generación de PDF con resumen diario usando ReportLab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    hoy = timezone.now().date()
    inicio = timezone.make_aware(datetime.combine(hoy, datetime.min.time()))
    fin = timezone.make_aware(datetime.combine(hoy, datetime.max.time()))

    ventas = Venta.objects.filter(fecha__gte=inicio, fecha__lte=fin, estado='completada')
    total_ventas = ventas.aggregate(t=Sum('total_venta'))['t'] or Decimal('0.00')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Reporte Diario de Operaciones - {hoy.strftime('%d/%m/%Y')}", styles['Title']))
    elements.append(Spacer(1, 15))

    tabla_data = [
        ["Concepto", "Valor COP"],
        ["Total Ventas Registradas", f"${total_ventas:,.2f}"],
        ["Número de Operaciones", str(ventas.count())]
    ]
    elements.append(Table(tabla_data))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_diario_{hoy}.pdf"'
    return response


# ==============================================================================
# MÓDULO DE GESTIÓN DE PELUQUEROS Y PERSONAL
# ==============================================================================

@login_required
def peluqueros_list(request):
    """Listado y gestión completa de peluqueros y personal operativo."""
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    rol = request.GET.get('rol', '')

    trabajadores = Trabajador.objects.all().annotate(
        total_atenciones=Count('servicios_realizados'),
        total_adelantos=Count('adelantos'),
        total_liquidaciones=Count('liquidaciones')
    )

    if q:
        trabajadores = trabajadores.filter(
            Q(nombre__icontains=q) | Q(documento__icontains=q) | Q(telefono__icontains=q)
        )
    if estado == 'activo':
        trabajadores = trabajadores.filter(activo=True)
    elif estado == 'inactivo':
        trabajadores = trabajadores.filter(activo=False)
    if rol:
        trabajadores = trabajadores.filter(rol=rol)

    return render(request, 'peluqueria/peluqueros_list.html', {
        'trabajadores': trabajadores,
        'q': q,
        'estado_sel': estado,
        'rol_sel': rol,
    })


@login_required
def peluquero_crear(request):
    """Registra un nuevo peluquero o trabajador en el sistema."""
    if request.method == 'POST':
        form = TrabajadorForm(request.POST)
        if form.is_valid():
            trabajador = form.save()
            messages.success(request, f"Trabajador/Peluquero '{trabajador.nombre}' registrado exitosamente.")
            return redirect('peluqueros_list')
    else:
        form = TrabajadorForm(initial={'rol': 'peluquero', 'porcentaje_comision_peluqueria': Decimal('50.00'), 'activo': True})
    return render(request, 'peluqueria/peluquero_form.html', {
        'form': form,
        'titulo': 'Nuevo Peluquero / Trabajador'
    })


@login_required
def peluquero_editar(request, pk):
    """Edita los datos de un peluquero o trabajador sin alterar su historial financiero."""
    trabajador = get_object_or_404(Trabajador, pk=pk)
    if request.method == 'POST':
        form = TrabajadorForm(request.POST, instance=trabajador)
        if form.is_valid():
            form.save()
            messages.success(request, f"Datos de '{trabajador.nombre}' actualizados correctamente.")
            return redirect('peluqueros_list')
    else:
        form = TrabajadorForm(instance=trabajador)
    return render(request, 'peluqueria/peluquero_form.html', {
        'form': form,
        'trabajador': trabajador,
        'titulo': f'Editar: {trabajador.nombre}'
    })


@login_required
def peluquero_detalle(request, pk):
    """Ficha de perfil e historial financiero de servicios, adelantos y liquidaciones del peluquero."""
    trabajador = get_object_or_404(Trabajador, pk=pk)
    atenciones = trabajador.servicios_realizados.select_related('servicio', 'mascota', 'cliente').order_by('-fecha')[:25]
    adelantos = trabajador.adelantos.order_by('-fecha')[:15]
    liquidaciones = trabajador.liquidaciones.order_by('-fecha_jornada')[:15]

    total_cobrado_historico = trabajador.servicios_realizados.aggregate(t=Sum('valor_neto'))['t'] or Decimal('0.00')
    total_comisiones_historico = trabajador.servicios_realizados.aggregate(t=Sum('comision_calculada'))['t'] or Decimal('0.00')

    return render(request, 'peluqueria/peluquero_detalle.html', {
        'trabajador': trabajador,
        'atenciones': atenciones,
        'adelantos': adelantos,
        'liquidaciones': liquidaciones,
        'total_cobrado_historico': total_cobrado_historico,
        'total_comisiones_historico': total_comisiones_historico,
    })


@login_required
@require_POST
def peluquero_toggle_activo(request, pk):
    """Activa o desactiva un peluquero para impedir nuevas atenciones sin borrar su historial."""
    trabajador = get_object_or_404(Trabajador, pk=pk)
    trabajador.activo = not trabajador.activo
    trabajador.save()
    estado_str = "activado" if trabajador.activo else "desactivado"
    messages.success(request, f"El peluquero '{trabajador.nombre}' ha sido {estado_str} exitosamente.")
    return redirect('peluqueros_list')


@login_required
@require_POST
def peluquero_eliminar(request, pk):
    """
    Elimina un peluquero SOLO si no tiene historial financiero asociado.
    Si tiene atenciones, adelantos o liquidaciones, bloquea la eliminación y ofrece desactivar.
    """
    trabajador = get_object_or_404(Trabajador, pk=pk)
    tiene_atenciones = trabajador.servicios_realizados.exists()
    tiene_adelantos = trabajador.adelantos.exists()
    tiene_liquidaciones = trabajador.liquidaciones.exists()

    if tiene_atenciones or tiene_adelantos or tiene_liquidaciones:
        messages.error(
            request,
            f"No se puede eliminar a '{trabajador.nombre}' porque posee registros financieros asociados "
            f"(atenciones, adelantos o liquidaciones). Puedes desactivarlo para que no aparezca en nuevas atenciones sin alterar la contabilidad."
        )
        return redirect('peluqueros_list')

    nombre = trabajador.nombre
    trabajador.delete()
    messages.success(request, f"El trabajador '{nombre}' fue eliminado exitosamente al no tener historial vinculado.")
    return redirect('peluqueros_list')


# ==============================================================================
# MÓDULO DE GESTIÓN DE PROVEEDORES
# ==============================================================================

@login_required
def proveedores_list(request):
    """Listado y gestión completa de proveedores de mercancía."""
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')

    proveedores = Proveedor.objects.all().annotate(
        total_compras=Count('compras')
    )

    if q:
        proveedores = proveedores.filter(
            Q(nombre__icontains=q) | Q(contacto__icontains=q) | Q(nit__icontains=q) | Q(telefono__icontains=q)
        )
    if estado == 'activo':
        proveedores = proveedores.filter(activo=True)
    elif estado == 'inactivo':
        proveedores = proveedores.filter(activo=False)

    return render(request, 'compras/proveedores_list.html', {
        'proveedores': proveedores,
        'q': q,
        'estado_sel': estado,
    })


@login_required
def proveedor_crear(request):
    """Registra un nuevo proveedor en el sistema."""
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            prov = form.save()
            messages.success(request, f"Proveedor '{prov.nombre}' registrado exitosamente.")
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('proveedores_list')
    else:
        form = ProveedorForm(initial={'activo': True})
    return render(request, 'compras/proveedor_form.html', {
        'form': form,
        'titulo': 'Nuevo Proveedor'
    })


@login_required
def proveedor_editar(request, pk):
    """Edita la información de un proveedor existente."""
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, f"Proveedor '{proveedor.nombre}' actualizado con éxito.")
            return redirect('proveedores_list')
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'compras/proveedor_form.html', {
        'form': form,
        'proveedor': proveedor,
        'titulo': f'Editar: {proveedor.nombre}'
    })


@login_required
def proveedor_detalle(request, pk):
    """Detalle del proveedor y compras asociadas."""
    proveedor = get_object_or_404(Proveedor, pk=pk)
    compras = proveedor.compras.order_by('-fecha')[:25]
    total_compras_valor = compras.aggregate(t=Sum('total'))['t'] or Decimal('0.00')

    return render(request, 'compras/proveedor_detalle.html', {
        'proveedor': proveedor,
        'compras': compras,
        'total_compras_valor': total_compras_valor,
    })


@login_required
@require_POST
def proveedor_toggle_activo(request, pk):
    """Activa o desactiva un proveedor para compras sin borrar su historial."""
    proveedor = get_object_or_404(Proveedor, pk=pk)
    proveedor.activo = not proveedor.activo
    proveedor.save()
    estado_str = "activado" if proveedor.activo else "desactivado"
    messages.success(request, f"Proveedor '{proveedor.nombre}' ha sido {estado_str}.")
    return redirect('proveedores_list')


@login_required
@require_POST
def proveedor_eliminar(request, pk):
    """
    Elimina un proveedor SOLO si no tiene compras históricas registradas.
    Si tiene compras, bloquea la eliminación protegiendo la integridad referencial.
    """
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if proveedor.compras.exists():
        messages.error(
            request,
            f"No se puede eliminar al proveedor '{proveedor.nombre}' porque posee facturas de compra históricas registradas. "
            f"Puedes desactivarlo para evitar nuevas compras sin afectar el inventario ni la contabilidad."
        )
        return redirect('proveedores_list')

    nombre = proveedor.nombre
    proveedor.delete()
    messages.success(request, f"Proveedor '{nombre}' eliminado exitosamente al no tener compras asociadas.")
    return redirect('proveedores_list')

