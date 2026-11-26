
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from django.contrib.auth import authenticate
from backend_coffee_api.models import PerfilUsuario, Categoria, Producto, ConfiguracionSistema
from backend_coffee_api.models import TurnoCaja, Pedido, DetallePedido, Preparacion
from backend_coffee_api.models import Entrega
from backend_coffee_api.models import MovimientoCaja, VentaCaja
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from backend_coffee_api.models import (VarianteProducto,Ingrediente,RecetaDetalle,Extra,ExtraPermitido,)

class UserSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()
    es_admin_principal = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'rol', 'es_admin_principal')
        read_only_fields = fields

    def get_rol(self, obj):
        grupo = obj.groups.first()
        return grupo.name if grupo else None

    def get_es_admin_principal(self, obj):
        return ConfiguracionSistema.objects.filter(
            pk=1,
            administrador_principal_id=obj.id
        ).exists()



class PerfilUsuarioSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = ('id', 'user', 'telefono', 'creation', 'update')


class InstalacionAdminSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    confirmar_password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Este nombre de usuario ya existe.')
        return value

    def validate(self, data):
        if data['password'] != data['confirmar_password']:
            raise serializers.ValidationError({'confirmar_password': 'Las contraseñas no coinciden.'})

        usuario = User(username=data['username'], first_name=data['first_name'], last_name=data['last_name'], email=data['email'])

        try:
            validate_password(data['password'], user=usuario)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': error.messages})

        return data


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        usuario = authenticate(username=data['username'], password=data['password'])

        if usuario is None:
            raise serializers.ValidationError('Usuario o contraseña incorrectos, o cuenta desactivada.')

        grupos = list(usuario.groups.values_list('name', flat=True))

        if len(grupos) != 1 or grupos[0] not in ['admin', 'colaborador', 'cocinero']:
            raise serializers.ValidationError('El usuario no tiene un rol válido asignado.')

        data['user'] = usuario
        return data



class EmpleadoSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()
    telefono = serializers.SerializerMethodField()
    es_admin_principal = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name', 'last_name',
            'email', 'telefono', 'rol', 'is_active',
            'date_joined', 'es_admin_principal'
        )
        read_only_fields = fields

    def get_rol(self, obj):
        grupo = obj.groups.first()
        return grupo.name if grupo else None

    def get_telefono(self, obj):
        perfil = getattr(obj, 'perfil', None)
        return perfil.telefono if perfil else ''

    def get_es_admin_principal(self, obj):
        return ConfiguracionSistema.objects.filter(
            pk=1,
            administrador_principal_id=obj.id
        ).exists()



class DatosEmpleadoSerializer(serializers.Serializer):
    username = serializers.RegexField(regex=r'^[\w.@+-]+\Z', max_length=150, required=False)
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    rol = serializers.ChoiceField(choices=['admin', 'colaborador', 'cocinero'], required=False)
    is_active = serializers.BooleanField(required=False)
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    confirmar_password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    def validate_username(self, value):
        usuario = self.context.get('usuario')
        existentes = User.objects.filter(username__iexact=value)

        if usuario:
            existentes = existentes.exclude(pk=usuario.pk)

        if existentes.exists():
            raise serializers.ValidationError('Este nombre de usuario ya está registrado.')

        return value

    def validate_email(self, value):
        usuario = self.context.get('usuario')
        existentes = User.objects.filter(email__iexact=value)

        if usuario:
            existentes = existentes.exclude(pk=usuario.pk)

        if existentes.exists():
            raise serializers.ValidationError('Este correo electrónico ya está registrado.')

        return value

    def validate(self, data):
        password = data.get('password')
        confirmacion = data.get('confirmar_password')

        if password is not None or confirmacion is not None:
            if password is None or confirmacion is None or password != confirmacion:
                raise serializers.ValidationError({'confirmar_password': 'Las contraseñas no coinciden.'})

            usuario = self.context.get('usuario') or User()

            for campo in ['username', 'first_name', 'last_name', 'email']:
                if campo in data:
                    setattr(usuario, campo, data[campo])

            try:
                validate_password(password, user=usuario)
            except DjangoValidationError as error:
                raise serializers.ValidationError({'password': error.messages})

        return data


class CrearEmpleadoSerializer(DatosEmpleadoSerializer):
    def validate(self, data):
        requeridos = ['username', 'first_name', 'last_name', 'email', 'rol', 'password', 'confirmar_password']
        faltantes = {campo: 'Este campo es obligatorio.' for campo in requeridos if campo not in data}

        if faltantes:
            raise serializers.ValidationError(faltantes)

        return super().validate(data)


class EditarEmpleadoSerializer(DatosEmpleadoSerializer):
    pass



class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'
        read_only_fields = ('id', 'creation', 'update')

    def validate_nombre(self, value):
        categorias = Categoria.objects.filter(nombre__iexact=value.strip())

        if self.instance:
            categorias = categorias.exclude(pk=self.instance.pk)

        if categorias.exists():
            raise serializers.ValidationError('Ya existe una categoría con este nombre.')

        return value.strip()



class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)

    class Meta:
        model = Producto
        fields = ('id', 'categoria', 'categoria_nombre', 'nombre', 'descripcion', 'precio', 'disponible', 'tiempo_preparacion', 'imagen', 'creation', 'update')
        read_only_fields = ('id', 'categoria_nombre', 'creation', 'update')

    def validate_nombre(self, value):
        return value.strip()

    def validate_precio(self, value):
        if value < 0:
            raise serializers.ValidationError('El precio no puede ser negativo.')
        return value

    def validate_tiempo_preparacion(self, value):
        if value < 1:
            raise serializers.ValidationError('El tiempo de preparación debe ser mayor a cero.')
        return value

    def validate(self, data):
        categoria = data.get('categoria', self.instance.categoria if self.instance else None)
        disponible = data.get('disponible', self.instance.disponible if self.instance else True)

        if categoria and disponible and not categoria.activo:
            raise serializers.ValidationError({'categoria': 'No puedes habilitar un producto dentro de una categoría inactiva.'})

        return data



class AperturaCajaSerializer(serializers.Serializer):
    fondo_inicial = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)



class TurnoCajaSerializer(serializers.ModelSerializer):
    colaborador_nombre = serializers.CharField(
        source='colaborador.username',
        read_only=True
    )

    cantidad_pedidos = serializers.SerializerMethodField()

    class Meta:
        model = TurnoCaja
        fields = (
            'id',
            'colaborador',
            'colaborador_nombre',
            'fondo_inicial',
            'apertura',
            'cierre',
            'estado',
            'efectivo_esperado_cierre',
            'efectivo_declarado',
            'diferencia',
            'cantidad_pedidos'
        )
        read_only_fields = fields

    def get_cantidad_pedidos(self, obj):
        return VentaCaja.objects.filter(turno=obj).count()



class ProductoPedidoSerializer(serializers.Serializer):
    producto = serializers.IntegerField(min_value=1)
    cantidad = serializers.IntegerField(min_value=1, max_value=30)


class CrearPedidoSerializer(serializers.Serializer):
    metodo_pago = serializers.ChoiceField(choices=Pedido.MetodoPago.choices)
    efectivo_recibido = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    detalles = ProductoPedidoSerializer(many=True, allow_empty=False)

    def validate(self, data):
        detalles = data['detalles']
        productos = [detalle['producto'] for detalle in detalles]

        if len(productos) != len(set(productos)):
            raise serializers.ValidationError({'detalles': 'No puedes repetir el mismo producto. Agrupa las cantidades.'})

        if sum(detalle['cantidad'] for detalle in detalles) > 30:
            raise serializers.ValidationError({'detalles': 'No puedes registrar más de 30 unidades por pedido.'})

        if data['metodo_pago'] == Pedido.MetodoPago.EFECTIVO and 'efectivo_recibido' not in data:
            raise serializers.ValidationError({'efectivo_recibido': 'Indica cuánto efectivo recibiste.'})

        if data['metodo_pago'] == Pedido.MetodoPago.TERMINAL and 'efectivo_recibido' in data:
            raise serializers.ValidationError({'efectivo_recibido': 'No debes enviar efectivo en pagos con terminal.'})

        return data


class DetallePedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetallePedido
        fields = ('id', 'producto', 'nombre_producto', 'precio_unitario', 'cantidad', 'subtotal')
        read_only_fields = fields


class PedidoSerializer(serializers.ModelSerializer):
    cajero_nombre = serializers.CharField(source='cajero.username', read_only=True)
    detalles = DetallePedidoSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = ('id', 'cajero', 'cajero_nombre', 'total', 'metodo_pago', 'pago_confirmado', 'efectivo_recibido', 'cambio', 'estado', 'fecha', 'detalles')
        read_only_fields = fields


class PreparacionSerializer(serializers.ModelSerializer):
    responsable_nombre = serializers.CharField(source='responsable.username', read_only=True, default=None)

    class Meta:
        model = Preparacion
        fields = ('id', 'detalle', 'numero_unidad', 'responsable', 'responsable_nombre', 'estado', 'fecha_inicio', 'fecha_fin')
        read_only_fields = fields


class DetalleCocinaSerializer(serializers.ModelSerializer):
    preparaciones = PreparacionSerializer(many=True, read_only=True)

    class Meta:
        model = DetallePedido
        fields = ('id', 'producto', 'nombre_producto', 'cantidad', 'preparaciones')
        read_only_fields = fields


class PedidoCocinaSerializer(serializers.ModelSerializer):
    detalles = DetalleCocinaSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = ('id', 'estado', 'fecha', 'detalles')
        read_only_fields = fields


class ActualizarPreparacionSerializer(serializers.Serializer):
    accion = serializers.ChoiceField(choices=['iniciar', 'finalizar'])



class RegistrarEntregaSerializer(serializers.Serializer):
    pedido = serializers.IntegerField(min_value=1)
    observaciones = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class PedidoEntregaSerializer(serializers.ModelSerializer):
    detalles = DetallePedidoSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = ('id', 'estado', 'total', 'metodo_pago', 'fecha', 'detalles')
        read_only_fields = fields


class EntregaSerializer(serializers.ModelSerializer):
    pedido = PedidoEntregaSerializer(read_only=True)
    responsable_nombre = serializers.CharField(source='responsable.username', read_only=True)

    class Meta:
        model = Entrega
        fields = ('id', 'pedido', 'responsable', 'responsable_nombre', 'fecha', 'observaciones')
        read_only_fields = fields


class RegistrarMovimientoCajaSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=MovimientoCaja.Tipo.choices)
    monto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    motivo = serializers.CharField(max_length=255, allow_blank=False)


class MovimientoCajaSerializer(serializers.ModelSerializer):
    colaborador_nombre = serializers.CharField(source='colaborador.username', read_only=True)

    class Meta:
        model = MovimientoCaja
        fields = ('id', 'turno', 'colaborador', 'colaborador_nombre', 'tipo', 'monto', 'motivo', 'fecha')
        read_only_fields = fields


class CerrarCajaSerializer(serializers.Serializer):
    efectivo_declarado = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class VentaCajaSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(source='pedido.total', max_digits=12, decimal_places=2, read_only=True)
    metodo_pago = serializers.CharField(source='pedido.metodo_pago', read_only=True)

    class Meta:
        model = VentaCaja
        fields = ('id', 'turno', 'pedido', 'total', 'metodo_pago', 'fecha')
        read_only_fields = fields


class FiltroReporteSerializer(serializers.Serializer):
    fecha_inicio = serializers.DateField(required=False)
    fecha_fin = serializers.DateField(required=False)

    def validate(self, data):
        hoy = timezone.localdate()
        inicio = data.get('fecha_inicio', hoy - timedelta(days=29))
        fin = data.get('fecha_fin', hoy)

        if inicio > fin:
            raise serializers.ValidationError({'fecha_fin': 'La fecha final no puede ser anterior a la inicial.'})

        if (fin - inicio).days > 365:
            raise serializers.ValidationError('El periodo de consulta no puede superar 366 días.')

        data['fecha_inicio'] = inicio
        data['fecha_fin'] = fin
        return data

# =====================================================
# SERIALIZADORES DE PERSONALIZACIÓN DE PRODUCTOS
# =====================================================


# =====================================================
# VARIANTES DE PRODUCTOS
# =====================================================

class VarianteProductoSerializer(serializers.ModelSerializer):

    producto_nombre = serializers.CharField(
        source='producto.nombre',
        read_only=True
    )

    class Meta:
        model = VarianteProducto

        fields = (
            'id',
            'producto',
            'producto_nombre',
            'nombre',
            'precio',
            'activo',
            'orden',
            'creation',
            'update'
        )

        read_only_fields = (
            'id',
            'creation',
            'update'
        )

    def validate_nombre(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'El tamaño o presentación debe tener un nombre.'
            )

        return value

    def validate_precio(self, value):

        if value < Decimal('0.00'):
            raise serializers.ValidationError(
                'El precio no puede ser negativo.'
            )

        return value


# =====================================================
# INGREDIENTES
# =====================================================

class IngredienteSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingrediente

        fields = (
            'id',
            'nombre',
            'descripcion',
            'unidad',
            'activo',
            'creation',
            'update'
        )

        read_only_fields = (
            'id',
            'creation',
            'update'
        )

    def validate_nombre(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'El ingrediente debe tener un nombre.'
            )

        return value


# =====================================================
# RECETAS POR VARIANTE
# =====================================================

class RecetaDetalleSerializer(serializers.ModelSerializer):

    variante_nombre = serializers.CharField(
        source='variante.nombre',
        read_only=True
    )

    ingrediente_nombre = serializers.CharField(
        source='ingrediente.nombre',
        read_only=True
    )

    unidad = serializers.CharField(
        source='ingrediente.unidad',
        read_only=True
    )

    class Meta:
        model = RecetaDetalle

        fields = (
            'id',
            'variante',
            'variante_nombre',
            'ingrediente',
            'ingrediente_nombre',
            'unidad',
            'cantidad',
            'creation',
            'update'
        )

        read_only_fields = (
            'id',
            'creation',
            'update'
        )

    def validate_cantidad(self, value):

        if value <= Decimal('0'):
            raise serializers.ValidationError(
                'La cantidad debe ser mayor que cero.'
            )

        return value


# =====================================================
# EXTRAS
# =====================================================

class ExtraSerializer(serializers.ModelSerializer):

    class Meta:
        model = Extra

        fields = (
            'id',
            'nombre',
            'descripcion',
            'precio',
            'activo',
            'creation',
            'update'
        )

        read_only_fields = (
            'id',
            'creation',
            'update'
        )

    def validate_nombre(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'El extra debe tener un nombre.'
            )

        return value

    def validate_precio(self, value):

        if value < Decimal('0.00'):
            raise serializers.ValidationError(
                'El precio no puede ser negativo.'
            )

        return value


# =====================================================
# EXTRAS PERMITIDOS POR PRODUCTO
# =====================================================

class ExtraPermitidoSerializer(serializers.ModelSerializer):

    producto_nombre = serializers.CharField(
        source='producto.nombre',
        read_only=True
    )

    extra_nombre = serializers.CharField(
        source='extra.nombre',
        read_only=True
    )

    class Meta:
        model = ExtraPermitido

        fields = (
            'id',
            'producto',
            'producto_nombre',
            'extra',
            'extra_nombre',
            'obligatorio',
            'cantidad_maxima',
            'activo'
        )

        read_only_fields = ('id',)

    def validate_cantidad_maxima(self, value):

        if value < 1:
            raise serializers.ValidationError(
                'La cantidad máxima debe ser al menos 1.'
            )

        return value

    def validate(self, attrs):

        extra = attrs.get(
            'extra',
            self.instance.extra if self.instance else None
        )

        activo = attrs.get(
            'activo',
            self.instance.activo if self.instance else True
        )

        if extra and activo and not extra.activo:
            raise serializers.ValidationError({
                'extra': (
                    'No puedes habilitar un extra inactivo.'
                )
            })

        return attrs
