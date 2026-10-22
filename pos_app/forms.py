"""
forms.py - Formularios completos y validados para el sistema POS Pet Shop y Peluquería
"""
from django import forms
from decimal import Decimal
from .models import (
    Producto, Categoria, Cliente, Mascota,
    Trabajador, ServicioPeluqueria, Proveedor,
    Compra, Egreso, SesionCaja, AdelantoPeluquero
)


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Alimentos, Juguetes, Farmacia'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción breve'}),
        }


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'nombre', 'sku', 'codigo_interno', 'categoria',
            'precio_compra', 'precio_venta', 'stock',
            'stock_minimo', 'unidad_medida', 'descripcion', 'activo'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código de barras escaneable'}),
            'codigo_interno': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código interno opcional'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'precio_compra': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'precio_venta': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        pc = cleaned_data.get('precio_compra')
        pv = cleaned_data.get('precio_venta')
        if pc is not None and pv is not None and pv < pc:
            self.add_error('precio_venta', 'El precio de venta no puede ser menor al costo/precio de compra.')
        return cleaned_data


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'documento', 'direccion', 'email', 'observaciones']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre y apellidos del propietario'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono o WhatsApp principal'}),
            'documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cédula o NIT opcional'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección de residencia'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notas adicionales'}),
        }


class MascotaForm(forms.ModelForm):
    class Meta:
        model = Mascota
        fields = ['cliente', 'nombre', 'especie', 'raza', 'tamano', 'edad_aproximada', 'observaciones_peluqueria']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la mascota'}),
            'especie': forms.Select(attrs={'class': 'form-select'}),
            'raza': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Schnauzer, Poodle, Criollo'}),
            'tamano': forms.Select(attrs={'class': 'form-select'}),
            'edad_aproximada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 2 años / 5 meses'}),
            'observaciones_peluqueria': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Comportamiento en baño, nudos, alergias en piel...'}),
        }


class TrabajadorForm(forms.ModelForm):
    """Formulario para gestión de peluqueros y personal operativo."""
    class Meta:
        model = Trabajador
        fields = ['nombre', 'telefono', 'documento', 'rol', 'porcentaje_comision_peluqueria', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo del trabajador o peluquero'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono o celular de contacto'}),
            'documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cédula o documento de identidad'}),
            'rol': forms.Select(attrs={'class': 'form-select'}),
            'porcentaje_comision_peluqueria': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0', 'max': '100'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise forms.ValidationError("El nombre completo es obligatorio.")
        return nombre

    def clean_documento(self):
        doc = self.cleaned_data.get('documento', '').strip() if self.cleaned_data.get('documento') else ''
        if doc:
            # Validar que no haya otro trabajador con la misma cédula
            qs = Trabajador.objects.filter(documento__iexact=doc)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Ya existe otro trabajador registrado con este número de documento.")
        return doc or None


class ServicioPeluqueriaForm(forms.ModelForm):
    class Meta:
        model = ServicioPeluqueria
        fields = ['nombre', 'descripcion', 'precio_sugerido', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Baño Completo, Corte Higiénico'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Detalle del servicio'}),
            'precio_sugerido': forms.NumberInput(attrs={'class': 'form-control', 'step': '100', 'min': '0'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProveedorForm(forms.ModelForm):
    """Formulario para creación y edición de proveedores."""
    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto', 'telefono', 'nit', 'direccion', 'email', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre comercial o razón social'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asesor comercial o contacto'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono o WhatsApp'}),
            'nit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIT o documento fiscal (opcional)'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección física o ciudad'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ventas@proveedor.com'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise forms.ValidationError("El nombre o razón social del proveedor es obligatorio.")
        return nombre

    def clean_nit(self):
        nit = self.cleaned_data.get('nit', '').strip() if self.cleaned_data.get('nit') else ''
        if nit:
            qs = Proveedor.objects.filter(nit__iexact=nit)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Ya existe un proveedor registrado con este NIT / documento.")
        return nit or None


class EgresoForm(forms.ModelForm):
    class Meta:
        model = Egreso
        fields = ['nombre', 'categoria', 'beneficiario', 'trabajador_asociado', 'monto', 'metodo_pago', 'descripcion', 'comprobante']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Concepto del egreso'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Persona que recibe el pago'}),
            'trabajador_asociado': forms.Select(attrs={'class': 'form-select'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '100'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones'}),
            'comprobante': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostrar sólo trabajadores activos para asignar pagos de nómina
        self.fields['trabajador_asociado'].queryset = Trabajador.objects.filter(activo=True)


class AdelantoPeluqueroForm(forms.ModelForm):
    class Meta:
        model = AdelantoPeluquero
        fields = ['peluquero', 'monto', 'medio_entrega', 'motivo']
        widgets = {
            'peluquero': forms.Select(attrs={'class': 'form-select'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'min': '1000', 'step': '1000', 'placeholder': 'Monto del adelanto'}),
            'medio_entrega': forms.Select(attrs={'class': 'form-select'}),
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Adelanto para almuerzo o urgencia'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo peluqueros activos pueden recibir nuevos adelantos
        self.fields['peluquero'].queryset = Trabajador.objects.filter(activo=True, rol='peluquero')


class AperturaCajaForm(forms.Form):
    monto_inicial = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, initial=Decimal('0.00'),
        label="Efectivo Inicial en Caja (Base)",
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'placeholder': '0.00'})
    )
    observaciones = forms.CharField(
        required=False, label="Observaciones de Apertura",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Billetes y monedas de base'})
    )


class CierreCajaForm(forms.Form):
    efectivo_real = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=0,
        label="Efectivo Físico Contado en Caja ($)",
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Total contado en billetes y monedas'})
    )
    observaciones = forms.CharField(
        required=False, label="Observaciones de Cierre",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notas sobre diferencias o justificaciones'})
    )


class CitaPeluqueriaForm(forms.ModelForm):
    """Formulario para agendar y editar citas de peluquería canina."""
    class Meta:
        from .models import CitaPeluqueria
        model = CitaPeluqueria
        fields = ['cliente', 'mascota', 'servicio', 'peluquero', 'fecha_cita', 'hora_inicio', 'duracion_minutos', 'estado', 'observaciones']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select', 'id': 'selectClienteCita'}),
            'mascota': forms.Select(attrs={'class': 'form-select', 'id': 'selectMascotaCita'}),
            'servicio': forms.Select(attrs={'class': 'form-select'}),
            'peluquero': forms.Select(attrs={'class': 'form-select'}),
            'fecha_cita': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'duracion_minutos': forms.NumberInput(attrs={'class': 'form-control', 'min': '15', 'step': '15'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Particularidades del corte o mascota...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['peluquero'].queryset = Trabajador.objects.filter(activo=True, rol='peluquero')
        self.fields['servicio'].queryset = ServicioPeluqueria.objects.filter(activo=True)
        self.fields['peluquero'].required = False

    def clean(self):
        cleaned_data = super().clean()
        cliente = cleaned_data.get('cliente')
        mascota = cleaned_data.get('mascota')
        peluquero = cleaned_data.get('peluquero')
        fecha = cleaned_data.get('fecha_cita')
        hora = cleaned_data.get('hora_inicio')
        duracion = cleaned_data.get('duracion_minutos') or 60
        estado = cleaned_data.get('estado')

        # Validar coherencia cliente - mascota
        if cliente and mascota and mascota.cliente != cliente:
            raise forms.ValidationError(f"La mascota '{mascota.nombre}' no pertenece al cliente '{cliente.nombre}'.")

        # Validar solapamiento de horarios para un mismo peluquero en citas no canceladas
        if peluquero and fecha and hora and estado != 'cancelada':
            from datetime import datetime, timedelta
            from .models import CitaPeluqueria

            inicio_dt = datetime.combine(fecha, hora)
            fin_dt = inicio_dt + timedelta(minutes=duracion)

            # Buscar otras citas activas en la misma fecha para el mismo peluquero
            otras_citas = CitaPeluqueria.objects.filter(
                peluquero=peluquero,
                fecha_cita=fecha
            ).exclude(estado='cancelada')

            if self.instance.pk:
                otras_citas = otras_citas.exclude(pk=self.instance.pk)

            for cita in otras_citas:
                c_inicio = datetime.combine(cita.fecha_cita, cita.hora_inicio)
                c_fin = c_inicio + timedelta(minutes=cita.duracion_minutos)
                # Detección de solapamiento
                if (inicio_dt < c_fin) and (fin_dt > c_inicio):
                    raise forms.ValidationError(
                        f"El peluquero '{peluquero.nombre}' ya tiene la cita #{cita.pk} ({cita.mascota.nombre}) agendada de "
                        f"{cita.hora_inicio.strftime('%H:%M')} a {c_fin.strftime('%H:%M')}. Elija otro horario o estilista."
                    )

        return cleaned_data
