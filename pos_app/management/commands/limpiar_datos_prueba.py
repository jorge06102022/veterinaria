"""
limpiar_datos_prueba.py
Comando para limpiar todos los datos transaccionales y de prueba de PetPOS Pro,
dejando el sistema en estado cero para producción.

Conserva:
- Categorías esenciales
- Catálogo de Servicios de Peluquería
- Trabajadores/Peluqueros activos (o permite reiniciarlos si se desea)
- Migraciones y estructura de tablas
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from pos_app.models import (
    PagoLiquidacion,
    LiquidacionPeluquero,
    AdelantoPeluquero,
    AtencionPeluqueria,
    DetalleVenta,
    PagoVenta,
    Venta,
    DetalleCompra,
    Compra,
    Egreso,
    SesionCaja,
    MovimientoInventario,
    Mascota,
    Cliente,
    Producto,
    Proveedor,
    Trabajador,
)

class Command(BaseCommand):
    help = "Limpia de forma segura y en orden referencial todos los datos de prueba de PetPOS Pro."

    def add_arguments(self, parser):
        parser.add_argument(
            '--incluir-trabajadores',
            action='store_true',
            help='Si se especifica, también elimina los trabajadores de prueba para crearlos desde cero en producción.',
        )

    def handle(self, *args, **options):
        self.stdout.write("Iniciando limpieza controlada de datos de prueba en PetPOS Pro...")
        incluir_trabajadores = options.get('incluir_trabajadores', False)

        with transaction.atomic():
            # 1. Liquidaciones y pagos
            c_pago_liq = PagoLiquidacion.objects.count()
            PagoLiquidacion.objects.all().delete()
            self.stdout.write(f"  [OK] Pagos de Liquidacion eliminados: {c_pago_liq}")

            c_liq = LiquidacionPeluquero.objects.count()
            LiquidacionPeluquero.objects.all().delete()
            self.stdout.write(f"  [OK] Liquidaciones de Peluquero eliminadas: {c_liq}")

            c_ade = AdelantoPeluquero.objects.count()
            AdelantoPeluquero.objects.all().delete()
            self.stdout.write(f"  [OK] Adelantos a Peluqueros eliminados: {c_ade}")

            # 2. Ventas y atenciones de peluquería
            c_atn = AtencionPeluqueria.objects.count()
            AtencionPeluqueria.objects.all().delete()
            self.stdout.write(f"  [OK] Atenciones de Peluqueria eliminadas: {c_atn}")

            c_det_vta = DetalleVenta.objects.count()
            DetalleVenta.objects.all().delete()
            self.stdout.write(f"  [OK] Detalles de Ventas eliminados: {c_det_vta}")

            c_pago_vta = PagoVenta.objects.count()
            PagoVenta.objects.all().delete()
            self.stdout.write(f"  [OK] Pagos de Ventas eliminados: {c_pago_vta}")

            c_vta = Venta.objects.count()
            Venta.objects.all().delete()
            self.stdout.write(f"  [OK] Ventas eliminadas: {c_vta}")

            # 3. Compras y detalles de compras
            c_det_cmp = DetalleCompra.objects.count()
            DetalleCompra.objects.all().delete()
            self.stdout.write(f"  [OK] Detalles de Compras eliminados: {c_det_cmp}")

            c_cmp = Compra.objects.count()
            Compra.objects.all().delete()
            self.stdout.write(f"  [OK] Compras eliminadas: {c_cmp}")

            # 4. Egresos operativos
            c_egr = Egreso.objects.count()
            Egreso.objects.all().delete()
            self.stdout.write(f"  [OK] Egresos operativos eliminados: {c_egr}")

            # 5. Sesiones de caja y arqueos
            c_caja = SesionCaja.objects.count()
            SesionCaja.objects.all().delete()
            self.stdout.write(f"  [OK] Sesiones de Caja / Arqueos eliminados: {c_caja}")

            # 6. Movimientos de inventario
            c_mov = MovimientoInventario.objects.count()
            MovimientoInventario.objects.all().delete()
            self.stdout.write(f"  [OK] Movimientos de inventario eliminados: {c_mov}")

            # 7. Mascotas y Clientes
            c_masc = Mascota.objects.count()
            Mascota.objects.all().delete()
            self.stdout.write(f"  [OK] Mascotas de prueba eliminadas: {c_masc}")

            c_cli = Cliente.objects.count()
            Cliente.objects.all().delete()
            self.stdout.write(f"  [OK] Clientes de prueba eliminados: {c_cli}")

            # 8. Productos y Proveedores de prueba
            c_prod = Producto.objects.count()
            Producto.objects.all().delete()
            self.stdout.write(f"  [OK] Productos de prueba eliminados: {c_prod}")

            c_prov = Proveedor.objects.count()
            Proveedor.objects.all().delete()
            self.stdout.write(f"  [OK] Proveedores de prueba eliminados: {c_prov}")

            # 9. Trabajadores de prueba (opcional)
            if incluir_trabajadores:
                c_trab = Trabajador.objects.count()
                Trabajador.objects.all().delete()
                self.stdout.write(f"  [OK] Trabajadores de prueba eliminados: {c_trab}")

        self.stdout.write(self.style.SUCCESS("Limpieza de datos de prueba finalizada exitosamente. Sistema en estado cero."))
