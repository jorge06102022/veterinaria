import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pos_project.settings')
django.setup()

import urllib.request
import urllib.parse
import http.cookiejar
import re

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Login
res = opener.open('http://127.0.0.1:8000/login/')
html = res.read().decode('utf-8')
m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
token = m.group(1) if m else ''

data = urllib.parse.urlencode({'username': 'tatiana', 'password': 'tati2026', 'csrfmiddlewaretoken': token}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/login/', data=data, headers={'Referer': 'http://127.0.0.1:8000/login/'})
opener.open(req)

routes = [
    ('/', 'Panel Principal'),
    ('/pos/', 'Punto de Venta POS'),
    ('/api/productos/', 'API Busqueda Productos'),
    ('/api/stock-bajo/', 'API Stock Bajo'),
    ('/ventas/', 'Historial de Ventas'),
    ('/inventario/', 'Inventario de Productos'),
    ('/inventario/nuevo/', 'Crear Producto'),
    ('/caja/', 'Control de Caja'),
    ('/caja/abrir/', 'Abrir Caja (GET)'),
    ('/peluqueria/', 'Peluqueria Dashboard'),
    ('/peluqueria/adelanto/', 'Registrar Adelanto'),
    ('/peluqueros/', 'Listado Peluqueros'),
    ('/peluqueros/nuevo/', 'Crear Peluquero'),
    ('/clientes/', 'Listado Clientes'),
    ('/clientes/nuevo/', 'Crear Cliente'),
    ('/mascotas/nueva/', 'Crear Mascota'),
    ('/compras/', 'Listado Compras'),
    ('/compras/nueva/', 'Registrar Compra'),
    ('/proveedores/', 'Listado Proveedores'),
    ('/proveedores/nuevo/', 'Crear Proveedor'),
    ('/egresos/', 'Listado y Registro Egresos'),
    ('/reportes/', 'Reportes Financieros'),
    ('/reporte-diario/', 'Reporte Diario PDF'),
]

for r, name in routes:
    try:
        resp = opener.open('http://127.0.0.1:8000' + r)
        code = resp.getcode()
        url_final = resp.geturl()
        ct = resp.headers.get('Content-Type', '')
        print(f"[OK {code}] {name} ({r}) -> {ct} ({url_final})")
    except Exception as e:
        print(f"[ERR] {name} ({r}) -> {e}")
