"""
init_admin.py - Inicializa de forma segura e idempotente el usuario administrador
de producción para PetPOS Pro.
Credenciales iniciales:
- Usuario: tatiana (o configurable vía DJANGO_SUPERUSER_USERNAME)
- Password: tati2026 (o configurable vía DJANGO_SUPERUSER_PASSWORD)
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Crea o actualiza de forma segura e idempotente el administrador inicial 'tatiana' y remueve usuarios de prueba."

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default=os.environ.get('DJANGO_SUPERUSER_USERNAME', 'tatiana'),
            help='Nombre de usuario administrador'
        )
        parser.add_argument(
            '--password',
            default=os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'tati2026'),
            help='Contraseña inicial del administrador'
        )
        parser.add_argument(
            '--email',
            default=os.environ.get('DJANGO_SUPERUSER_EMAIL', 'tatiana@petpospro.com'),
            help='Correo electrónico del administrador'
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']

        # 1. Crear o actualizar el administrador solicitado
        user, created = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Usuario administrador '{username}' creado exitosamente con acceso total."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Usuario administrador '{username}' actualizado exitosamente con acceso total."))

        # 2. Remover usuarios de prueba previos para dejar exclusivamente la cuenta autorizada
        usuarios_antiguos = User.objects.exclude(username=username)
        total_removidos = usuarios_antiguos.count()
        if total_removidos > 0:
            nombres = list(usuarios_antiguos.values_list('username', flat=True))
            usuarios_antiguos.delete()
            self.stdout.write(f"Usuarios de prueba eliminados ({total_removidos}): {', '.join(nombres)}")
        else:
            self.stdout.write("No habia usuarios adicionales de prueba.")

        self.stdout.write(self.style.SUCCESS(f"Listo: La base de datos cuenta unicamente con el administrador '{username}'."))
