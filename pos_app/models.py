"""
models.py - Modelos de base de datos para POS: Pet Shop, Peluquería Canina y Tienda de Mascotas.
Diseñado con soporte de transacciones, integridad referencial, separación de medios de pago,
cierre de caja ciego/comparativo, comisiones al 50%, adelantos, compras y egresos.
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


# ==============================================================================
# 1. CATEGORÍAS Y PRODUCTOS (INVENTARIO)
# ==============================================================================

class Categoria(models.Model):
    """Categorías de productos para tienda de mascotas."""
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    """
    Catálogo de productos de la tienda de animales.
    Mantiene compatibilidad con 'sku' como código principal / de barras.
    """
    UNIDAD_CHOICES = [
        ('und', 'Unidad'),
        ('kg', 'Kilogramo'),
        ('g', 'Gramo'),
        ('l', 'Litro'),
        ('ml', 'Mililitro'),
        ('paq', 'Paquete'),
    ]

    nombre = models.CharField(max_length=200, verbose_name="Nombre del Producto")
    sku = models.CharField(
        max_length=60, unique=True, verbose_name="Código de Barras / SKU",
        help_text="Código leído con pistola lectora USB o código interno único"
    )
    codigo_interno = models.CharField(
        max_length=60, blank=True, null=True, verbose_name="Código Interno Opcional"
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Categoría", related_name="productos"
    )
    precio_compra = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Precio de Compra (Costo)"
    )
    precio_venta = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Precio de Venta"
    )
    stock = models.IntegerField(default=0, verbose_name="Stock Disponible")
    stock_minimo = models.IntegerField(
        default=5, verbose_name="Stock Mínimo (Alerta)",
        help_text="Alerta cuando el stock baje o iguale este nivel"
    )
    unidad_medida = models.CharField(
        max_length=10, choices=UNIDAD_CHOICES, default='und', verbose_name="Unidad de Medida"
    )
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.sku})"

    @property
    def margen_ganancia(self):
        """Margen de ganancia porcentual."""
        if self.precio_compra > 0:
            return round(((self.precio_venta - self.precio_compra) / self.precio_compra) * Decimal('100'), 2)
        return Decimal('0.00')

    @property
    def ganancia_unitaria(self):
        """Ganancia neta por unidad vendida."""
        return self.precio_venta - self.precio_compra

    @property
    def stock_bajo(self):
        return self.stock <= self.stock_minimo

    @property
    def sin_stock(self):
        return self.stock <= 0


class MovimientoInventario(models.Model):
    """Kardex / Historial de entradas, salidas y ajustes de inventario."""
    TIPO_CHOICES = [
        ('entrada_compra', 'Entrada por Compra'),
        ('salida_venta', 'Salida por Venta'),
        ('ajuste_positivo', 'Ajuste Manual (+)'),
        ('ajuste_negativo', 'Ajuste Manual (-)'),
        ('anulacion_venta', 'Devolución / Anulación Venta (+)'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    cantidad = models.IntegerField(help_text="Cantidad positiva de unidades involucradas")
    stock_anterior = models.IntegerField()
    stock_nuevo = models.IntegerField()
    motivo = models.CharField(max_length=255, blank=True, null=True)
    referencia_origen = models.CharField(max_length=100, blank=True, null=True, help_text="Ej: Venta #12, Compra #4")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-fecha']


# ==============================================================================
# 2. CLIENTES Y MASCOTAS
# ==============================================================================

class Cliente(models.Model):
    """Propietarios de mascotas y clientes de la tienda."""
    nombre = models.CharField(max_length=150, verbose_name="Nombre Completo")
    telefono = models.CharField(max_length=50, verbose_name="Teléfono / WhatsApp")
    documento = models.CharField(max_length=50, blank=True, null=True, verbose_name="Documento / Cédula")
    direccion = models.CharField(max_length=250, blank=True, null=True, verbose_name="Dirección")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.telefono})"


class Mascota(models.Model):
    """Mascota asociada a un cliente para servicios de peluquería."""
    TAMANO_CHOICES = [
        ('pequeno', 'Pequeño (hasta 10 kg)'),
        ('mediano', 'Mediano (10 a 20 kg)'),
        ('grande', 'Grande (20 a 35 kg)'),
        ('gigante', 'Gigante (más de 35 kg)'),
    ]
    ESPECIE_CHOICES = [
        ('perro', 'Perro'),
        ('gato', 'Gato'),
        ('otro', 'Otro'),
    ]

    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="mascotas", verbose_name="Propietario"
    )
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Mascota")
    especie = models.CharField(max_length=20, choices=ESPECIE_CHOICES, default='perro', verbose_name="Especie")
    raza = models.CharField(max_length=100, blank=True, null=True, verbose_name="Raza")
    tamano = models.CharField(max_length=20, choices=TAMANO_CHOICES, default='pequeno', verbose_name="Tamaño")
    edad_aproximada = models.CharField(max_length=50, blank=True, null=True, verbose_name="Edad / F. Nacimiento")
    observaciones_peluqueria = models.TextField(
        blank=True, null=True, verbose_name="Notas de Peluquería / Cuidados",
        help_text="Alergias en piel, temperamento, corte preferido, etc."
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mascota"
        verbose_name_plural = "Mascotas"
        ordering = ['nombre']

    def __str__(self):
        dueno = self.cliente.nombre if self.cliente else "Sin dueño"
        return f"{self.nombre} ({self.raza or self.especie}) - Dueño: {dueno}"


# ==============================================================================
# 3. TRABAJADORES Y SERVICIOS DE PELUQUERÍA
# ==============================================================================

class Trabajador(models.Model):
    """
    Personal operativo (peluqueros, dependientes, personal de aseo/apoyo).
    No requiere cuenta de usuario Django, permitiendo control sin exponer el sistema.
    """
    ROL_CHOICES = [
        ('peluquero', 'Peluquero(a) Canino'),
        ('vendedor', 'Vendedor(a) / Dependiente'),
        ('apoyo', 'Auxiliar / Aseo / Mantenimiento'),
        ('otro', 'Otro'),
    ]

    nombre = models.CharField(max_length=150, verbose_name="Nombre Completo")
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono")
    documento = models.CharField(max_length=50, blank=True, null=True, verbose_name="Cédula / Documento")
    rol = models.CharField(max_length=30, choices=ROL_CHOICES, default='peluquero', verbose_name="Rol en el negocio")
    porcentaje_comision_peluqueria = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('50.00'),
        verbose_name="Porcentaje Comisión (%)",
        help_text="Porcentaje de comisión en servicios de peluquería (por defecto 50%)"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_ingreso = models.DateField(default=timezone.now, verbose_name="Fecha de Ingreso")

    class Meta:
        verbose_name = "Trabajador"
        verbose_name_plural = "Trabajadores"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.get_rol_display()})"


class ServicioPeluqueria(models.Model):
    """Catálogo de servicios de grooming y peluquería canina/felina."""
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Nombre del Servicio")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    precio_sugerido = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Precio Sugerido Base"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Servicio de Peluquería"
        verbose_name_plural = "Servicios de Peluquería"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} - ${self.precio_sugerido:,.0f}"


# ==============================================================================
# 4. SESIONES DE CAJA (APERTURA Y CIERRE CON SEPARACIÓN EFECTIVO / BANCO)
# ==============================================================================

class SesionCaja(models.Model):
    """
    Control de caja diaria.
    Diferencia estrictamente el efectivo físico de los pagos bancarios/electrónicos.
    """
    ESTADO_CHOICES = [
        ('abierta', 'Abierta'),
        ('cerrada', 'Cerrada'),
    ]

    fecha_apertura = models.DateTimeField(default=timezone.now)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    monto_inicial_efectivo = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Efectivo Inicial en Caja"
    )
    
    # Valores de cierre
    efectivo_esperado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    efectivo_real = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Efectivo Contado Físico")
    diferencia_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    banco_esperado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Total transferencias y medios electrónicos")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='abierta')
    observaciones_apertura = models.TextField(blank=True, null=True)
    observaciones_cierre = models.TextField(blank=True, null=True)
    usuario_apertura = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="cajas_abiertas")
    usuario_cierre = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="cajas_cerradas")

    class Meta:
        verbose_name = "Sesión de Caja"
        verbose_name_plural = "Sesiones de Caja"
        ordering = ['-fecha_apertura']

    def __str__(self):
        return f"Caja #{self.pk} - {self.fecha_apertura.strftime('%d/%m/%Y %H:%M')} [{self.estado.upper()}]"


# ==============================================================================
# 5. VENTAS, DETALLES Y PAGOS MULTI-MÉTODO
# ==============================================================================

class Venta(models.Model):
    """
    Venta de productos y/o servicios de peluquería en el POS.
    Permite pagos mixtos (efectivo + transferencia/tarjeta).
    """
    ESTADO_CHOICES = [
        ('completada', 'Completada'),
        ('anulada', 'Anulada'),
    ]

    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia Bancaria'),
        ('tarjeta', 'Tarjeta Débito/Crédito'),
        ('mixto', 'Pago Mixto (Efectivo + Electrónico)'),
        ('otro', 'Otro'),
    ]

    fecha = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Venta")
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas")
    sesion_caja = models.ForeignKey(SesionCaja, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas")

    # Totales monetarios
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_venta = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Venta")
    
    # Desglose de ganancias e ingresos
    total_costo_productos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_ganancia_productos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_servicios = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_comision_peluquero = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_ganancia = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name="Ganancia Neta Negocio",
        help_text="Ganancia productos + (Servicios - Comisiones peluquero)"
    )

    metodo_pago = models.CharField(
        max_length=20, choices=METODO_PAGO_CHOICES, default='efectivo', verbose_name="Método de Pago Principal"
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='completada')
    motivo_anulacion = models.TextField(blank=True, null=True)
    anulada_en = models.DateTimeField(null=True, blank=True)
    notas = models.TextField(blank=True, null=True, verbose_name="Notas")
    uuid_operacion = models.CharField(max_length=64, unique=True, null=True, blank=True, help_text="Para evitar doble submit")

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha']

    def __str__(self):
        return f"Venta #{self.pk} - {self.fecha.strftime('%d/%m/%Y %H:%M')} - ${self.total_venta:,.0f} [{self.estado}]"


class PagoVenta(models.Model):
    """
    Desglose exacto de medios de pago aplicados a una venta.
    Soporta pagos mixtos (ej: $20.000 efectivo + $30.000 transferencia = $50.000 total).
    """
    METODO_CHOICES = [
        ('efectivo', 'Efectivo Físico'),
        ('transferencia', 'Transferencia Bancaria (Nequi/Daviplata/Bancolombia)'),
        ('tarjeta', 'Tarjeta Débito/Crédito'),
        ('otro', 'Otro'),
    ]

    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='pagos')
    metodo = models.CharField(max_length=30, choices=METODO_CHOICES)
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    referencia = models.CharField(max_length=100, blank=True, null=True, help_text="Nro de comprobante/aprobación de transferencia")
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Pago de Venta"
        verbose_name_plural = "Pagos de Ventas"

    def __str__(self):
        return f"{self.get_metodo_display()}: ${self.monto:,.0f}"


class DetalleVenta(models.Model):
    """
    Línea de detalle para producto físico vendido.
    Conserva nombre histórico, sku y costo de adquisición.
    """
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles', verbose_name="Venta")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, verbose_name="Producto")
    nombre_producto = models.CharField(max_length=200, blank=True, default='')
    sku_producto = models.CharField(max_length=60, blank=True, default='')
    cantidad = models.IntegerField(verbose_name="Cantidad")
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio de Venta")
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio de Compra / Costo")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Subtotal")

    class Meta:
        verbose_name = "Detalle de Venta (Producto)"
        verbose_name_plural = "Detalles de Venta (Productos)"

    def __str__(self):
        return f"{self.cantidad}x {self.nombre_producto or self.producto.nombre} @ ${self.precio_venta:,.0f}"

    @property
    def ganancia(self):
        return (self.precio_venta - self.precio_compra) * self.cantidad

    def save(self, *args, **kwargs):
        if not self.nombre_producto and self.producto:
            self.nombre_producto = self.producto.nombre
            self.sku_producto = self.producto.sku
        self.subtotal = self.precio_venta * self.cantidad
        super().save(*args, **kwargs)


class AtencionPeluqueria(models.Model):
    """
    Registro individual de un servicio de peluquería prestado.
    Calcula de forma exacta la comisión (50% por defecto) y preserva el estado de liquidación.
    """
    ESTADO_LIQUIDACION_CHOICES = [
        ('pendiente', 'Pendiente de Liquidar'),
        ('liquidado', 'Liquidado en Jornada'),
        ('anulado', 'Anulado'),
    ]

    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='servicios_peluqueria', null=True, blank=True)
    servicio = models.ForeignKey(ServicioPeluqueria, on_delete=models.PROTECT, verbose_name="Servicio")
    nombre_servicio = models.CharField(max_length=150, blank=True, default='')
    mascota = models.ForeignKey(Mascota, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Mascota")
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cliente")
    peluquero = models.ForeignKey(Trabajador, on_delete=models.PROTECT, related_name="servicios_realizados", verbose_name="Peluquero(a)")
    
    precio_cobrado = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Cobrado")
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Descuento")
    valor_neto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Base Neto")
    
    porcentaje_comision = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('50.00'))
    comision_calculada = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Comisión del Peluquero")
    parte_negocio = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Parte del Negocio")
    
    estado_liquidacion = models.CharField(max_length=20, choices=ESTADO_LIQUIDACION_CHOICES, default='pendiente')
    liquidada_en = models.ForeignKey('LiquidacionPeluquero', on_delete=models.SET_NULL, null=True, blank=True, related_name="servicios_incluidos")
    fecha = models.DateTimeField(default=timezone.now)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Atención de Peluquería"
        verbose_name_plural = "Atenciones de Peluquería"
        ordering = ['-fecha']

    def save(self, *args, **kwargs):
        if not self.nombre_servicio and self.servicio:
            self.nombre_servicio = self.servicio.nombre
        self.valor_neto = self.precio_cobrado - (self.descuento or Decimal('0.00'))
        if self.valor_neto < 0:
            self.valor_neto = Decimal('0.00')
        # Regla: comisión sobre valor neto efectivamente cobrado
        comision_pct = (self.porcentaje_comision or Decimal('50.00')) / Decimal('100.00')
        self.comision_calculada = round(self.valor_neto * comision_pct, 2)
        self.parte_negocio = self.valor_neto - self.comision_calculada
        super().save(*args, **kwargs)

    def __str__(self):
        pelu = self.peluquero.nombre if self.peluquero else "Sin asignar"
        masc = self.mascota.nombre if self.mascota else "Ocasional"
        return f"{self.nombre_servicio} - {masc} (${self.valor_neto:,.0f}) Peluquero: {pelu}"


# ==============================================================================
# 6. MÓDULO ESPECIAL: ADELANTOS, LIQUIDACIÓN Y PAGOS DEL PELUQUERO
# ==============================================================================

class AdelantoPeluquero(models.Model):
    """
    Adelanto de dinero entregado al peluquero a cuenta de sus comisiones.
    Reduce el saldo por pagar al cierre y afecta la caja física o banco una sola vez.
    """
    MEDIO_ENTREGA_CHOICES = [
        ('efectivo', 'Efectivo de Caja'),
        ('transferencia', 'Transferencia Bancaria'),
    ]
    ESTADO_CHOICES = [
        ('imputado', 'Imputado a Liquidación'),
        ('pendiente', 'Pendiente de Liquidar'),
        ('anulado', 'Anulado'),
    ]

    peluquero = models.ForeignKey(Trabajador, on_delete=models.PROTECT, related_name="adelantos")
    sesion_caja = models.ForeignKey(SesionCaja, on_delete=models.SET_NULL, null=True, blank=True, related_name="adelantos")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto del Adelanto")
    medio_entrega = models.CharField(max_length=20, choices=MEDIO_ENTREGA_CHOICES, default='efectivo')
    fecha = models.DateTimeField(default=timezone.now)
    motivo = models.CharField(max_length=200, blank=True, null=True, verbose_name="Motivo / Observación")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    liquidada_en = models.ForeignKey('LiquidacionPeluquero', on_delete=models.SET_NULL, null=True, blank=True, related_name="adelantos_incluidos")

    class Meta:
        verbose_name = "Adelanto a Peluquero"
        verbose_name_plural = "Adelantos a Peluqueros"
        ordering = ['-fecha']

    def __str__(self):
        return f"Adelanto #{self.pk} - {self.peluquero.nombre}: ${self.monto:,.0f} [{self.get_medio_entrega_display()}]"


class LiquidacionPeluquero(models.Model):
    """
    Cierre y liquidación de jornada para el peluquero.
    Fórmula estricta:
    Saldo por pagar = saldo_anterior_pendiente + comisiones_periodo - adelantos_periodo - pagos_realizados.
    """
    ESTADO_CHOICES = [
        ('abierta', 'Abierta / En Revisión'),
        ('parcial', 'Parcialmente Pagada'),
        ('liquidada', 'Cerrada y Pagada'),
        ('anulada', 'Anulada'),
    ]

    peluquero = models.ForeignKey(Trabajador, on_delete=models.PROTECT, related_name="liquidaciones")
    fecha_jornada = models.DateField(default=timezone.now, verbose_name="Fecha de la Jornada")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    total_cobrado_servicios = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_comision = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Comisiones de la Jornada")
    saldo_anterior = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Saldo Pendiente de Días Anteriores")
    total_adelantos = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Adelantos Imputados")
    total_pagos = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Pagos de Cierre Entregados")
    saldo_pendiente = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Saldo Final por Pagar")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='abierta')
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Liquidación de Peluquero"
        verbose_name_plural = "Liquidaciones de Peluqueros"
        ordering = ['-fecha_jornada', '-id']

    def recalcular(self):
        """Recalcula comisiones, adelantos y saldo final."""
        servicios = self.servicios_incluidos.exclude(estado_liquidacion='anulado')
        self.total_cobrado_servicios = sum((s.valor_neto for s in servicios), Decimal('0.00'))
        self.total_comision = sum((s.comision_calculada for s in servicios), Decimal('0.00'))
        
        adelantos = self.adelantos_incluidos.exclude(estado='anulado')
        self.total_adelantos = sum((a.monto for a in adelantos), Decimal('0.00'))
        
        pagos = self.pagos_asociados.exclude(estado='anulado')
        self.total_pagos = sum((p.monto for p in pagos), Decimal('0.00'))
        
        # Saldo por pagar = saldo anterior + comisión - adelantos - pagos
        self.saldo_pendiente = (self.saldo_anterior + self.total_comision) - self.total_adelantos - self.total_pagos
        
        if self.saldo_pendiente <= Decimal('0.00'):
            self.estado = 'liquidada'
        elif self.total_pagos > Decimal('0.00'):
            self.estado = 'parcial'
        else:
            self.estado = 'abierta'
        self.save()

    def __str__(self):
        return f"Liquidación {self.peluquero.nombre} ({self.fecha_jornada}) - Saldo: ${self.saldo_pendiente:,.0f} [{self.estado}]"


class PagoLiquidacion(models.Model):
    """
    Pago entregado al peluquero como cierre de liquidación (total o parcial).
    Registra el medio de pago para afectar caja física o banco exactamente una vez.
    """
    MEDIO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo de Caja'),
        ('transferencia', 'Transferencia Bancaria'),
    ]
    ESTADO_CHOICES = [
        ('confirmado', 'Confirmado'),
        ('anulado', 'Anulado'),
    ]

    liquidacion = models.ForeignKey(LiquidacionPeluquero, on_delete=models.CASCADE, related_name="pagos_asociados")
    sesion_caja = models.ForeignKey(SesionCaja, on_delete=models.SET_NULL, null=True, blank=True, related_name="pagos_peluquero")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto Pagado")
    medio_pago = models.CharField(max_length=20, choices=MEDIO_PAGO_CHOICES, default='efectivo')
    referencia = models.CharField(max_length=100, blank=True, null=True)
    fecha = models.DateTimeField(default=timezone.now)
    observacion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='confirmado')

    class Meta:
        verbose_name = "Pago de Liquidación"
        verbose_name_plural = "Pagos de Liquidaciones"

    def __str__(self):
        return f"Pago #{self.pk} - ${self.monto:,.0f} ({self.get_medio_pago_display()})"


# ==============================================================================
# 7. PROVEEDORES Y COMPRAS DE INVENTARIO
# ==============================================================================

class Proveedor(models.Model):
    """Proveedores de mercancía y productos para animales."""
    nombre = models.CharField(max_length=150, verbose_name="Nombre / Empresa")
    contacto = models.CharField(max_length=100, blank=True, null=True, verbose_name="Persona de Contacto")
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono")
    nit = models.CharField(max_length=50, blank=True, null=True, verbose_name="NIT / Documento")
    direccion = models.CharField(max_length=200, blank=True, null=True, verbose_name="Dirección")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Compra(models.Model):
    """
    Orden de compra recibida a proveedor.
    Actualiza existencias y costo unitario de los productos comprados.
    """
    ESTADO_CHOICES = [
        ('recibida_pagada', 'Recibida y Pagada'),
        ('recibida_pendiente', 'Recibida con Pago Pendiente (Crédito)'),
        ('anulada', 'Anulada'),
    ]
    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia Bancaria'),
        ('credito', 'A Crédito / Pendiente'),
    ]

    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="compras")
    sesion_caja = models.ForeignKey(SesionCaja, on_delete=models.SET_NULL, null=True, blank=True, related_name="compras")
    numero_factura_proveedor = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nro. Factura Proveedor")
    fecha = models.DateTimeField(default=timezone.now)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES, default='efectivo')
    estado = models.CharField(max_length=25, choices=ESTADO_CHOICES, default='recibida_pagada')
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ['-fecha']

    def __str__(self):
        return f"Compra #{self.pk} - {self.proveedor.nombre} - ${self.total:,.0f}"


class DetalleCompra(models.Model):
    """Renglón de producto comprado."""
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.IntegerField()
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.costo_unitario
        super().save(*args, **kwargs)


# ==============================================================================
# 8. EGRESOS OPERATIVOS Y PAGOS AL RESTO DEL PERSONAL
# ==============================================================================

class Egreso(models.Model):
    """
    Gastos generales del negocio y pagos a trabajadores (distintos al peluquero).
    Mantiene compatibilidad con campos originales y añade categorías enriquecidas,
    beneficiario y vínculo trazable a caja.
    """
    CATEGORIA_CHOICES = [
        ('personal', 'Pago de Personal (Jornales / Sueldos)'),
        ('servicios', 'Servicios Públicos (Luz, Agua, Internet)'),
        ('arriendo', 'Arriendo del Local'),
        ('mantenimiento', 'Mantenimiento y Reparaciones'),
        ('compras_menores', 'Compras Menores / Insumos de Aseo'),
        ('otro', 'Otros Gastos Operativos'),
    ]

    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia Bancaria'),
        ('tarjeta', 'Tarjeta'),
        ('otro', 'Otro'),
    ]

    nombre = models.CharField(
        max_length=150,
        verbose_name="Concepto del Gasto",
        help_text="Ej: Pago de jornada a ayudante, Pago de luz, arriendo"
    )
    categoria = models.CharField(
        max_length=30, choices=CATEGORIA_CHOICES, default='otro', verbose_name="Categoría"
    )
    beneficiario = models.CharField(
        max_length=150, blank=True, null=True,
        verbose_name="Beneficiario / Nombre del Trabajador",
        help_text="Nombre de quien recibe el dinero (ej: Juan Pérez)"
    )
    trabajador_asociado = models.ForeignKey(
        Trabajador, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pagos_egresos", verbose_name="Trabajador (si está registrado)"
    )
    descripcion = models.TextField(
        blank=True, null=True, verbose_name="Descripción / Observaciones"
    )
    monto = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Monto Gastado"
    )
    metodo_pago = models.CharField(
        max_length=20, choices=METODO_PAGO_CHOICES, default='efectivo', verbose_name="Método de Pago"
    )
    sesion_caja = models.ForeignKey(
        SesionCaja, on_delete=models.SET_NULL, null=True, blank=True, related_name="egresos"
    )
    fecha = models.DateTimeField(default=timezone.now, verbose_name="Fecha del Gasto")
    comprobante = models.FileField(
        upload_to='egresos/comprobantes/', blank=True, null=True, verbose_name="Comprobante (opcional)"
    )

    class Meta:
        verbose_name = "Egreso"
        verbose_name_plural = "Egresos"
        ordering = ['-fecha']

    def __str__(self):
        ben = f" ({self.beneficiario})" if self.beneficiario else ""
        return f"{self.nombre}{ben} - ${self.monto:,.0f} [{self.get_metodo_pago_display()}]"