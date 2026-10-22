import urllib.request, urllib.parse, http.cookiejar, re

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

# Proveedores List
r_list = opener.open('http://127.0.0.1:8000/proveedores/')
html_list = r_list.read().decode('utf-8')
print('=== PROVEEDORES LIST HTML CHECK ===')
print('Has header title Proveedores:', 'Proveedores' in html_list)
print('Has subtitle:', 'Gestiona tus proveedores' in html_list)
print('Has Total Proveedores stat:', 'Total Proveedores' in html_list)
print('Has Proveedores Activos stat:', 'Proveedores Activos' in html_list)
print('Has Proveedores Inactivos stat:', 'Proveedores Inactivos' in html_list)
print('Has button Nuevo Proveedor:', 'Nuevo Proveedor' in html_list)
print('Has btn-accent class:', 'btn-accent' in html_list)
print('Has table-pos class:', 'table-pos' in html_list)
print('Has search input:', 'name="q"' in html_list)

# Proveedor Form
r_form = opener.open('http://127.0.0.1:8000/proveedores/nuevo/')
html_form = r_form.read().decode('utf-8')
print('\n=== PROVEEDOR FORM HTML CHECK ===')
print('Has Informacion Comercial:', 'Información Comercial' in html_form)
print('Has Informacion de Contacto:', 'Información de Contacto' in html_form)
print('Has Ubicacion:', 'Ubicación' in html_form)
print('Has field nombre:', 'name="nombre"' in html_form)
print('Has field nit:', 'name="nit"' in html_form)
print('Has field telefono:', 'name="telefono"' in html_form)
print('Has field email:', 'name="email"' in html_form)
print('Has field direccion:', 'name="direccion"' in html_form)
print('Has field activo:', 'name="activo"' in html_form)
print('Has submit button Registrar Proveedor:', 'Registrar Proveedor' in html_form)
