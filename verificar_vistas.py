import urllib.request
import urllib.parse
import http.cookiejar
import re

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. Obtener pantalla de login y token CSRF
res = opener.open('http://127.0.0.1:8000/login/')
html = res.read().decode('utf-8')
m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
token = m.group(1) if m else ''
print("Token CSRF obtenido:", bool(token))

# 2. Iniciar sesión con la cuenta oficial tatiana / tati2026
data = urllib.parse.urlencode({
    'username': 'tatiana',
    'password': 'tati2026',
    'csrfmiddlewaretoken': token
}).encode()

req = urllib.request.Request('http://127.0.0.1:8000/login/', data=data, headers={'Referer': 'http://127.0.0.1:8000/login/'})
res_login = opener.open(req)
print("Estado de autenticación de tatiana:", res_login.getcode())

# 3. Probar navegación por todos los módulos del sistema
endpoints = [
    ('Panel Principal (Dashboard)', 'http://127.0.0.1:8000/'),
    ('Punto de Venta (POS)', 'http://127.0.0.1:8000/pos/'),
    ('Control de Caja', 'http://127.0.0.1:8000/caja/'),
    ('Peluquería y Liquidaciones', 'http://127.0.0.1:8000/peluqueria/'),
    ('Directorio de Clientes', 'http://127.0.0.1:8000/clientes/'),
    ('Inventario de Productos', 'http://127.0.0.1:8000/inventario/'),
    ('Compras a Proveedores', 'http://127.0.0.1:8000/compras/'),
    ('Registrar Compra', 'http://127.0.0.1:8000/compras/nueva/'),
    ('Listado de Proveedores', 'http://127.0.0.1:8000/proveedores/'),
    ('Crear Proveedor', 'http://127.0.0.1:8000/proveedores/nuevo/'),
    ('Listado de Peluqueros', 'http://127.0.0.1:8000/peluqueros/'),
    ('Crear Peluquero', 'http://127.0.0.1:8000/peluqueros/nuevo/'),
    ('Egresos y Salidas', 'http://127.0.0.1:8000/egresos/'),
    ('Reportes Financieros', 'http://127.0.0.1:8000/reportes/'),
    ('Historial de Ventas', 'http://127.0.0.1:8000/ventas/'),
]

for nombre, url in endpoints:
    try:
        r = opener.open(url)
        content = r.read().decode('utf-8')
        final_url = r.geturl()
        if 'login' in final_url and 'next' in final_url:
            print(f"[REDIRECCION LOGIN NO DESEADA] {nombre} ({url}) -> redirigió a {final_url}")
        else:
            print(f"[OK] {nombre} ({url}) -> HTTP {r.getcode()} ({len(content)} bytes)")
    except Exception as e:
        print(f"[ERROR] {nombre} ({url}) -> {e}")

