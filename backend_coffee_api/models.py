from django.conf import settings
from django.db import models
from django.db.models import Q


# ==========================================
# PERFILES DE USUARIOS
# ==========================================

class PerfilUsuario(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil')
    telefono = models.CharField(max_length=20, blank=True)
    creation = models.DateTimeField(auto_now_add=True)
    update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Perfil de {self.user.username}'


# ==========================================
# CATEGORÍAS
# ==========================================

class Categoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    creation = models.DateTimeField(auto_now_add=True)
    update = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        db_table = 'categorias'

    def __str__(self):
        return self.nombre


# ==========================================
# PRODUCTOS
# ==========================================


class Producto(models.Model):
    id = models.BigAutoField(primary_key=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='productos')
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    disponible = models.BooleanField(default=True)
    tiempo_preparacion = models.PositiveSmallIntegerField(default=5)
    imagen = models.ImageField(upload_to='productos/', null=True, blank=True)
    creation = models.DateTimeField(auto_now_add=True)
    update = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        db_table = 'productos'
        constraints = [
            models.CheckConstraint(condition=Q(precio__gte=0), name='producto_precio_positivo'),
            models.CheckConstraint(condition=Q(tiempo_preparacion__gte=1), name='producto_tiempo_preparacion_positivo')
        ]

    def __str__(self):
        return self.nombre

# ==========================================
# PEDIDOS
# ==========================================

class Pedido(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        PREPARACION = 'preparacion', 'En preparación'
        LISTO = 'listo', 'Listo'
        ENTREGADO = 'entregado', 'Entregado'
        CANCELADO = 'cancelado', 'Cancelado'

    class MetodoPago(models.TextChoices):
        EFECTIVO = 'efectivo', 'Efectivo'
        TERMINAL = 'terminal', 'Terminal'

    id = models.BigAutoField(primary_key=True)
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='pedidos')
    total = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=MetodoPago.choices)
    pago_confirmado = models.BooleanField(default=False)
    efectivo_recibido = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cambio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha = models.DateTimeField(auto_now_add=True)
    update = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha']
        db_table = 'pedidos'
        constraints = [
            models.CheckConstraint(condition=Q(total__gte=0), name='pedido_total_positivo'),
            models.CheckConstraint(condition=Q(cambio__gte=0), name='pedido_cambio_positivo')
        ]

    def __str__(self):
        return f'Pedido #{self.id}'


# ==========================================
# DETALLES DE PEDIDOS
# ==========================================

class DetallePedido(models.Model):
    id = models.BigAutoField(primary_key=True)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='ventas')
    nombre_producto = models.CharField(max_length=150)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']
        db_table = 'detalles_pedido'
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gte=1), name='detalle_cantidad_positiva'),
            models.CheckConstraint(condition=Q(precio_unitario__gte=0), name='detalle_precio_positivo'),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name='detalle_subtotal_positivo')
        ]

    def __str__(self):
        return f'{self.cantidad} x {self.nombre_producto}'


# ==========================================
# PREPARACIONES DE COCINA
# ==========================================

class Preparacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        PREPARACION = 'preparacion', 'En preparación'
        LISTO = 'listo', 'Listo'

    id = models.BigAutoField(primary_key=True)
    detalle = models.ForeignKey(DetallePedido, on_delete=models.CASCADE, related_name='preparaciones')
    numero_unidad = models.PositiveIntegerField()
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='preparaciones')
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']
        db_table = 'preparaciones'
        constraints = [
            models.UniqueConstraint(fields=['detalle', 'numero_unidad'], name='preparacion_unidad_unica'),
            models.CheckConstraint(condition=Q(numero_unidad__gte=1), name='preparacion_unidad_positiva')
        ]

    def __str__(self):
        return f'Preparación #{self.id} - {self.get_estado_display()}'


# ==========================================
# ENTREGAS
# ==========================================

class Entrega(models.Model):
    id = models.BigAutoField(primary_key=True)
    pedido = models.OneToOneField(Pedido, on_delete=models.PROTECT, related_name='entrega')
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='entregas')
    fecha = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha']
        db_table = 'entregas'

    def __str__(self):
        return f'Entrega del pedido #{self.pedido_id}'


# ==========================================
# TURNOS DE CAJA
# ==========================================

class TurnoCaja(models.Model):
    class Estado(models.TextChoices):
        ABIERTA = 'abierta', 'Abierta'
        CERRADA = 'cerrada', 'Cerrada'

    id = models.BigAutoField(primary_key=True)
    colaborador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='turnos_caja')
    fondo_inicial = models.DecimalField(max_digits=12, decimal_places=2)
    apertura = models.DateTimeField(auto_now_add=True)
    cierre = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTA)
    efectivo_esperado_cierre = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    efectivo_declarado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    diferencia = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-apertura']
        db_table = 'turnos_caja'
        constraints = [models.CheckConstraint(condition=Q(fondo_inicial__gte=0), name='turno_fondo_positivo')]

    def __str__(self):
        return f'Turno #{self.id} - {self.colaborador.username}'


# ==========================================
# MOVIMIENTOS DE CAJA
# ==========================================

class MovimientoCaja(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = 'entrada', 'Entrada'
        RETIRO = 'retiro', 'Retiro'

    id = models.BigAutoField(primary_key=True)
    turno = models.ForeignKey(TurnoCaja, on_delete=models.PROTECT, related_name='movimientos')
    colaborador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='movimientos_caja')
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    motivo = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        db_table = 'movimientos_caja'
        constraints = [models.CheckConstraint(condition=Q(monto__gt=0), name='movimiento_monto_positivo')]

    def __str__(self):
        return f'{self.get_tipo_display()} - ${self.monto}'


# ==========================================
# VENTAS ASOCIADAS A CAJA
# ==========================================

class VentaCaja(models.Model):
    id = models.BigAutoField(primary_key=True)
    turno = models.ForeignKey(TurnoCaja, on_delete=models.PROTECT, related_name='ventas')
    pedido = models.OneToOneField(Pedido, on_delete=models.PROTECT, related_name='venta_caja')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        db_table = 'ventas_caja'

    def __str__(self):
        return f'Pedido #{self.pedido_id} - Turno #{self.turno_id}'


class ConfiguracionSistema(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    completada = models.BooleanField(default=False)
    fecha_configuracion = models.DateTimeField(null=True, blank=True)
    administrador_principal = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='configuracion_principal')

    class Meta:
        db_table = 'configuracion_sistema'

    def __str__(self):
        return 'Configuración inicial de Backend Coffee'
