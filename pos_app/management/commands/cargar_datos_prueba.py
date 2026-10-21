"""
cargar_datos_prueba.py - Generador de datos iniciales completos para Pet Shop y Peluquería Canina
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import random
from datetime import timedelta

from pos_app.models import (
    Categoria, Producto, Cliente, Mascota, Trabajador,
    ServicioPeluqueria, Proveedor, Compra, DetalleCompra,
    Venta, DetalleVenta, AtencionPeluqueria, PagoVenta,
    AdelantoPeluquero, LiquidacionPeluquero, Egreso, SesionCaja
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Carga datos de prueba realistas para Peluquería de Mascotas y Pet Shop'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando carga de datos de prueba para Pet Shop y Peluquería...')

        # 1. Superusuario Administrador
        admin_user, _ = User.objects.get_or_create(username='admin', defaults={'email': 'admin@petpos.com'})
        admin_user.set_password('admin123')
        admin_user.is_superuser = True
        admin_user.is_staff = True
        admin_user.save()
        self.stdout.write(self.style.SUCCESS('[OK] Superusuario verificado: admin / admin123'))

        # 2. Categorías de Tienda de Mascotas
        cats_data = [
            ('Alimento Perros', 'Concentrado, galletas y snacks caninos'),
            ('Alimento Gatos', 'Concentrado, paté y snacks felinos'),
            ('Accesorios & Juguetes', 'Collares, correas, pelotas y rascadores'),
            ('Farmacia & Cuidado', 'Antipulgas, champús medicados y vitaminas'),
            ('Higiene & Arena', 'Arena para gatos, toallas húmedas y pañales'),
        ]
        categorias = {}
        for nom, desc in cats_data:
            c, _ = Categoria.objects.get_or_create(nombre=nom, defaults={'descripcion': desc})
            categorias[nom] = c
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(categorias)} categorias creadas'))

        # 3. Catálogo de Productos con códigos de barras realistas
        prods_data = [
            ('Dog Chow Adultos 2kg', '770123456001', 'Alimento Perros', 22000, 32000, 35),
            ('Pro Plan Adulto Razas Medianas 3kg', '770123456002', 'Alimento Perros', 55000, 78000, 20),
            ('Snack Galletas CanAmor 200g', '770123456003', 'Alimento Perros', 4500, 7500, 45),
            ('Whiskas Pescado 1.5kg', '770123456004', 'Alimento Gatos', 18000, 26000, 30),
            ('Cat Chow Gatitos 1kg', '770123456005', 'Alimento Gatos', 14000, 21000, 25),
            ('Shampoo Canino Coco & Avena 500ml', '770123456006', 'Farmacia & Cuidado', 12000, 22000, 28),
            ('Pipeta Antipulgas Fipronil Perro Mediano', '770123456007', 'Farmacia & Cuidado', 15000, 28000, 40),
            ('Arena Sanitaria Aglomerante 5kg', '770123456008', 'Higiene & Arena', 16000, 25000, 50),
            ('Collar Ajustable Reflectivo Talla M', '770123456009', 'Accesorios & Juguetes', 8000, 16000, 18),
            ('Pelota Mordedora con Cuerda', '770123456010', 'Accesorios & Juguetes', 5000, 11000, 22),
            ('Cepillo Deslanador Furflex', '770123456011', 'Accesorios & Juguetes', 14000, 29000, 4), # stock bajo
        ]
        productos = []
        for nom, sku, cat_nom, pc, pv, st in prods_data:
            p, _ = Producto.objects.get_or_create(
                sku=sku,
                defaults={
                    'nombre': nom,
                    'categoria': categorias[cat_nom],
                    'precio_compra': Decimal(str(pc)),
                    'precio_venta': Decimal(str(pv)),
                    'stock': st,
                    'stock_minimo': 5,
                    'unidad_medida': 'und',
                }
            )
            productos.append(p)
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(productos)} productos creados'))

        # 4. Servicios de Peluquería
        servs_data = [
            ('Baño Básico & Secado', 'Baño, cepillado y corte de uñas', 28000),
            ('Peluquería Canina Completa', 'Baño, corte de raza, uñas y limpieza de oídos', 45000),
            ('Corte Higiénico & Deslanado', 'Despeje de zonas íntimas y retiro de pelo muerto', 32000),
            ('Baño Medicado Dermatológico', 'Champú antialérgico o antipulgas con masaje', 38000),
            ('Grooming Completo Razas Grandes', 'Baño y corte especial para Golden/Husky/Labrador', 65000),
        ]
        servicios = []
        for nom, desc, ps in servs_data:
            s, _ = ServicioPeluqueria.objects.get_or_create(nombre=nom, defaults={'descripcion': desc, 'precio_sugerido': Decimal(str(ps))})
            servicios.append(s)
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(servicios)} servicios de peluqueria configurados'))

        # 5. Personal / Peluqueros y Trabajadores
        peluquero_carlos, _ = Trabajador.objects.get_or_create(
            nombre='Carlos Rodríguez',
            defaults={'rol': 'peluquero', 'telefono': '3124567890', 'porcentaje_comision_peluqueria': Decimal('50.00')}
        )
        peluquera_maria, _ = Trabajador.objects.get_or_create(
            nombre='María Fernández',
            defaults={'rol': 'peluquero', 'telefono': '3157891234', 'porcentaje_comision_peluqueria': Decimal('50.00')}
        )
        ayudante_juan, _ = Trabajador.objects.get_or_create(
            nombre='Juan Pérez',
            defaults={'rol': 'apoyo', 'telefono': '3001234567', 'porcentaje_comision_peluqueria': Decimal('0.00')}
        )
        self.stdout.write(self.style.SUCCESS('[OK] Trabajadores y peluqueros registrados (comision 50%)'))

        # 6. Clientes y Mascotas
        clientes_data = [
            ('Andrés Morales', '3005551122', 'Max', 'perro', 'Golden Retriever', 'grande'),
            ('Carolina Vega', '3114443322', 'Luna', 'perro', 'Poodle Mini', 'pequeno'),
            ('Santiago Gómez', '3209998877', 'Milo', 'gato', 'Siamés', 'pequeno'),
            ('Valeria Ortiz', '3156667788', 'Toby', 'perro', 'Schnauzer', 'mediano'),
        ]
        for c_nom, tel, m_nom, esp, raza, tam in clientes_data:
            c, _ = Cliente.objects.get_or_create(nombre=c_nom, defaults={'telefono': tel})
            Mascota.objects.get_or_create(cliente=c, nombre=m_nom, defaults={'especie': esp, 'raza': raza, 'tamano': tam})
        self.stdout.write(self.style.SUCCESS('[OK] Clientes y mascotas creados'))

        # 7. Proveedores
        prov, _ = Proveedor.objects.get_or_create(
            nombre='Distribuidora Pet Colombia SAS',
            defaults={'contacto': 'Jorge Vendedor', 'telefono': '3188889900', 'nit': '900123456-1'}
        )
        self.stdout.write(self.style.SUCCESS('[OK] Proveedor verificado'))

        # 8. Sesión de Caja Activa para pruebas
        caja_activa = SesionCaja.objects.filter(estado='abierta').first()
        if not caja_activa:
            caja_activa = SesionCaja.objects.create(
                monto_inicial_efectivo=Decimal('100000.00'),
                usuario_apertura=admin_user,
                estado='abierta',
                observaciones_apertura='Caja base de demostracion $100.000 COP'
            )
            self.stdout.write(self.style.SUCCESS('[OK] Sesion de caja abierta creada con base $100.000 COP'))

        self.stdout.write(self.style.SUCCESS('\n[OK] Datos iniciales cargados con exito para Pet Shop y Peluqueria Canina.'))
