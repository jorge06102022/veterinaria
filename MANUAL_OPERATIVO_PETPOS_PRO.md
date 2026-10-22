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

## 3. CATÁLOGO ADMINISTRABLE DE SERVICIOS DE PELUQUERÍA

1. **Ruta:** `/servicios/` (o desde el menú lateral *Mascotas & Servicios > Servicios de Peluquería*).
2. **Creación desde Cero:** No se imponen servicios obligatorios en el arranque. El administrador puede dar de alta los servicios reales que ofrece el establecimiento (ej. *Baño y Secado*, *Corte de Raza*, *Deslanado*, *Corte Higiénico*), con su precio sugerido base en pesos (`DecimalField`).
3. **Protección Histórica Inviolable:**
   - Si se edita el precio sugerido de un servicio, las ventas y atenciones pasadas **conservan intacto** el precio cobrado y la comisión liquidada en su momento histórico.
   - Si un servicio cuenta con atenciones facturadas o citas en agenda, el sistema **bloquea su eliminación física** para proteger la integridad referencial y ofrece desactivarlo.
   - Los servicios desactivados no aparecen en el POS para nuevas ventas ni en el formulario de nuevas citas, pero se preservan en los reportes e históricos.
   - Si un servicio nuevo no posee atenciones ni citas asociadas, se puede eliminar físicamente de forma limpia con confirmación previa.

---

## 4. INTEGRIDAD FINANCIERA Y ARQUEO DE CAJA FÍSICA

### Reglas de Flujo de Efectivo en Gaveta
En PetPOS Pro v2.4 Enterprise, el efectivo esperado en caja se calcula de forma atómica y auditable:
$$\text{Efectivo Esperado} = \text{Monto Base} + \text{Ventas en Efectivo} - \text{Egresos Operativos en Efectivo} - \text{Compras en Efectivo} - \text{Adelantos de Peluqueros} - \text{Liquidaciones Pagadas en Efectivo}$$

1. **Apertura de Caja:** Debe realizarse diariamente antes de registrar ventas o egresos. Se ingresa el efectivo base físico en gaveta mediante POST protegido por CSRF.
2. **Compras de Mercancía en Efectivo:** Si se compra mercancía con dinero de la caja física, el sistema descuenta automáticamente el monto de la gaveta de la sesión activa y suma el stock al Kardex.
3. **Pagos Mixtos y Digitales:** Pagos con tarjeta o transferencia se acumulan en sus respectivas cuentas de control bancario, sin desfasar el arqueo del efectivo en mano.
4. **Cierre Ciego:** El cajero declara el efectivo físico contado. El sistema calcula la discrepancia (Sobrante o Faltante) y congela la sesión.

---

## 5. AGENDA DE PELUQUERÍA Y CONTROL DE SOLAPAMIENTO

1. **Ruta:** `/peluqueria/citas/`
2. **Asignación:** Se selecciona cliente, mascota, servicio específico del catálogo activo y peluquero asignado.
3. **Control Anti-Solapamiento:** El sistema valida a nivel de modelo y formulario en el servidor que el peluquero no tenga otra cita activa dentro de la ventana de tiempo calculada $(\text{Hora Inicio} \to \text{Hora Inicio} + \text{Duración en Minutos})$.
4. **Estados:** *Pendiente* $\to$ *Confirmada* $\to$ *En Proceso* $\to$ *Completada* / *Cancelada*.
5. **Cobro:** Las citas no facturan de forma ficticia ni generan comisiones anticipadas; el cobro se realiza a través del punto de venta POS garantizando el comprobante y el registro contable.

---

## 6. REGLAS DE COMISIÓN DE PELUQUEROS (50%)

- Los servicios de peluquería generan un 50% de comisión neta para el peluquero asignado sobre el valor efectivamente cobrado.
- Los adelantos registrados durante el periodo descuentan el saldo por pagar sin descontarse dos veces.
- Los saldos pendientes se arrastran automáticamente a la siguiente jornada sin duplicación.
- Las liquidaciones cerradas quedan congeladas en base de datos preservando el histórico financiero inmutable.

---

## 7. PRODUCTOS, KARDEX Y LECTOR DE CÓDIGO DE BARRAS

1. **Ruta:** `/pos/` e `/inventario/`.
2. **Lector de Código de Barras USB:** Opera en modo teclado emulando entrada rápida; al escanear el código SKU el producto se agrega directamente al carrito.
3. **Kardex:** Registra salidas por venta, entradas por compras y ajustes manuales con motivo y trazabilidad de usuario.

---

## 8. COMPRAS Y PROVEEDORES

1. **Ruta:** `/proveedores/` y `/compras/`.
2. **Detalle de Factura:** Disponible en `/compras/<id>/` con desglose de renglones, costos unitarios y método de pago (efectivo o banco).
3. **Protección de Proveedores:** No se permite eliminar proveedores con facturas de compra históricas registradas; se ofrece desactivación controlada.

---

## 9. BITÁCORA INMUTABLE DE AUDITORÍA

1. **Ruta:** `/auditoria/`
2. **Eventos Registrados:** Creación de citas, cambios de estado, compras de mercancía, egresos, creación/edición de servicios, aperturas y cierres de caja.
3. **Información Capturada:** Usuario, fecha y hora exacta, módulo, acción ejecutada, IP de origen y descripción detallada.

---

## 10. DESPLIEGUE EN RENDER CON POSTGRESQL

### Variables de Entorno Requeridas en Render Web Service:
- `SECRET_KEY` o `DJANGO_SECRET_KEY`: Cadena criptográfica aleatoria de 50+ caracteres.
- `DEBUG` o `DJANGO_DEBUG`: `False` (modo producción estricto).
- `ALLOWED_HOSTS`: Dominio asignado en Render (ej. `petpos-pro.onrender.com`).
- `DATABASE_URL`: URI de conexión provista por Render PostgreSQL (formato `postgres://usuario:clave@host:5432/dbname`).
- `CSRF_TRUSTED_ORIGINS`: `https://*.onrender.com` o el dominio propio en HTTPS.
- `DJANGO_SUPERUSER_USERNAME`: `tatiana`
- `DJANGO_SUPERUSER_PASSWORD`: Contraseña segura definida por el propietario.

### Comandos de Construcción y Arranque en Render:
- **Build Command:** `./build.sh` (actualiza pip, instala dependencias, ejecuta `collectstatic`, aplica `migrate` y ejecuta `init_admin`).
- **Start Command:** `./start.sh` (inicia el servidor WSGI Gunicorn con 4 workers en el puerto asignado).

---

## 11. COPIAS DE SEGURIDAD Y RECUPERACIÓN

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
