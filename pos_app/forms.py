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
    class Meta:
        model = Trabajador
        fields = ['nombre', 'telefono', 'documento', 'rol', 'porcentaje_comision_peluqueria', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono'}),
            'documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cédula'}),
            'rol': forms.Select(attrs={'class': 'form-select'}),
            'porcentaje_comision_peluqueria': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0', 'max': '100'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


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
    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto', 'telefono', 'nit', 'direccion', 'email', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la empresa distribuidora'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asesor comercial'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono'}),
            'nit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIT'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ventas@proveedor.com'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


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
