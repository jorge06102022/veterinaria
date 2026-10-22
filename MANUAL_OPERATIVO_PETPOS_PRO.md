# MANUAL DE OPERACIÓN Y DESPLIEGUE — PETPOS PRO v2.4 ENTERPRISE

Este manual contiene las directrices técnicas y operativas para la puesta en marcha, gestión diaria, administración contable y mantenimiento de **PetPOS Pro**.

---

## 1. INSTALACIÓN LOCAL Y PUESTA EN MARCHA (DESARROLLO)

### Requisitos del Sistema
- Python 3.11 o superior.
- Git.
- Navegador web moderno (Chrome, Edge, Firefox).

### Pasos de Inicio
1. **Clonar o abrir el repositorio:**
   ```bash
   cd pos_proyecto-main
   ```
2. **Crear y activar entorno virtual:**
   ```bash
   python -m venv venv
   # En Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   # En Linux / macOS:
   source venv/bin/activate
   ```
3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Aplicar migraciones:**
   ```bash
   python manage.py migrate
   ```
5. **Iniciar el servidor local:**
   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```
   *O mediante el ejecutable Windows:* `iniciar_pos.bat`.

---

## 2. GESTIÓN DEL ADMINISTRADOR PRINCIPAL

- **Usuario Administrador:** `tatiana`
- **Contraseña Inicial de Fábrica:** `tati2026`
- **Comando Idempotente:**
  El comando `python manage.py init_admin` garantiza la existencia del usuario administrador sin sobrescribir contraseñas modificadas una vez inicializado.
- **Cambio de Contraseña Seguro:**
  Se recomienda encarecidamente cambiar la clave inicial desde el panel administrativo (`/admin/`) o mediante el comando de Django:
  ```bash
  python manage.py changepassword tatiana
  ```

---

## 3. INTEGRIDAD FINANCIERA Y ARQUEO DE CAJA FÍSICA

### Reglas de Flujo de Efectivo en Gaveta
En PetPOS Pro v2.4 Enterprise, el efectivo esperado en caja se calcula de forma atómica y auditable:
$$\text{Efectivo Esperado} = \text{Monto Base} + \text{Ventas en Efectivo} - \text{Egresos Operativos en Efectivo} - \text{Compras en Efectivo} - \text{Adelantos de Peluqueros} - \text{Liquidaciones Pagadas en Efectivo}$$

1. **Apertura de Caja:** Debe realizarse diariamente antes de registrar ventas o egresos. Se ingresa el efectivo base físico en gaveta.
2. **Compras de Mercancía en Efectivo:** Si se compra mercancía con dinero de la caja física, el sistema descuenta automáticamente el monto de la gaveta de la sesión activa y suma el stock al Kardex.
3. **Pagos Mixtos y Digitales:** Pagos con tarjeta o transferencia se acumulan en sus respectivas cuentas de control bancario, sin desfasar el arqueo del efectivo en mano.
4. **Cierre Ciego:** El cajero declara el efectivo físico contado. El sistema calcula la discrepancia (Sobrante o Faltante) y congela la sesión.

---

## 4. AGENDA DE PELUQUERÍA Y CONTROL DE SOLAPAMIENTO

1. **Ruta:** `/peluqueria/citas/`
2. **Asignación:** Se selecciona cliente, mascota, servicio específico y peluquero asignado.
3. **Control Anti-Solapamiento:** El sistema valida a nivel de modelo y formulario que el peluquero no tenga otra cita activa dentro de la ventana de tiempo calculada $(\text{Hora Inicio} \to \text{Hora Inicio} + \text{Duración en Minutos})$.
4. **Estados:** *Pendiente* $\to$ *Confirmada* $\to$ *En Proceso* $\to$ *Completada* / *Cancelada*.
5. **Cobro:** Las citas no facturan de forma ficticia; se cobran a través del punto de venta POS garantizando el comprobante y el Kardex respectivo.

---

## 5. REGLAS DE COMISIÓN DE PELUQUEROS (50%)

- Los servicios de peluquería generan un 50% de comisión neta para el peluquero asignado.
- Los adelantos registrados durante el periodo descuentan el saldo por pagar.
- Las liquidaciones cerradas quedan congeladas en base de datos preservando el histórico financiero.

---

## 6. BITÁCORA INMUTABLE DE AUDITORÍA

1. **Ruta:** `/auditoria/`
2. **Eventos Registrados:** Creación de citas, cambios de estado, compras de mercancía, egresos, aperturas y cierres de caja.
3. **Información Capturada:** Usuario, fecha y hora exacta, módulo, acción ejecutada, IP de origen y descripción detallada.

---

## 7. DESPLIEGUE EN RENDER CON POSTGRESQL

### Variables de Entorno Requeridas en Render Web Service:
- `SECRET_KEY`: Cadena criptográfica aleatoria de 50+ caracteres.
- `DEBUG`: `False` (modo producción estricto).
- `ALLOWED_HOSTS`: Dominio asignado en Render (ej. `petpos-pro.onrender.com`).
- `DATABASE_URL`: URI de conexión provista por Render PostgreSQL (formato `postgres://usuario:clave@host:5432/dbname`).
- `CSRF_TRUSTED_ORIGINS`: `https://*.onrender.com` o el dominio propio.
- `DJANGO_SUPERUSER_USERNAME`: `tatiana`
- `DJANGO_SUPERUSER_PASSWORD`: Contraseña segura definida por el propietario.

### Comandos de Construcción y Arranque en Render:
- **Build Command:** `./build.sh` (actualiza pip, instala dependencias, ejecuta `collectstatic`, aplica `migrate` y ejecuta `init_admin`).
- **Start Command:** `./start.sh` (inicia el servidor WSGI Gunicorn con 4 workers en el puerto asignado).

---

## 8. COPIAS DE SEGURIDAD Y RECUPERACIÓN

### En Producción (PostgreSQL)
PetPOS Pro incluye el script automatizado [scripts/backup_restore.sh](file:///c:/Users/jorge%20ochoa/Downloads/pos_proyecto-main/scripts/backup_restore.sh):
- **Generar Respaldo:**
  ```bash
  export DATABASE_URL="postgres://..."
  ./scripts/backup_restore.sh backup_pg
  ```
- **Restaurar Respaldo:**
  ```bash
  ./scripts/backup_restore.sh restore_pg ./backups/petpos_pro_pg_TIMESTAMP.sql.gz
  ```

### En Desarrollo Local (SQLite)
- **Generar Volcado JSON:**
  ```bash
  ./scripts/backup_restore.sh backup_sqlite
  ```
  O directamente: `python manage.py dumpdata --indent 2 > backup.json`.
