
from django.db.models import Prefetch
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend_coffee_api.models import Categoria, Producto, VarianteProducto, ExtraPermitido
from backend_coffee_api.serializers import CategoriaSerializer, ProductoSerializer


# =====================================================
# MENÚ PÚBLICO DE BACKEND COFFEE
# =====================================================

class MenuPublicoView(APIView):

    # El menú puede consultarse sin iniciar sesión.
    authentication_classes = []
    permission_classes = [AllowAny]

    # =====================================================
    # CONSULTAR MENÚ PÚBLICO
    # =====================================================

    def get(self, request):

        # ==========================================
        # CATEGORÍAS ACTIVAS
        # ==========================================

        categorias = Categoria.objects.filter(
            activo=True
        ).order_by('nombre')

        # ==========================================
        # VARIANTES ACTIVAS
        # ==========================================

        variantes_activas = VarianteProducto.objects.filter(
            activo=True
        ).order_by('orden', 'id')

        # ==========================================
        # EXTRAS ACTIVOS Y PERMITIDOS
        # ==========================================

        extras_permitidos = ExtraPermitido.objects.filter(
            activo=True,
            extra__activo=True
        ).select_related('extra').order_by('id')

        # ==========================================
        # PRODUCTOS DISPONIBLES
        # ==========================================

        productos = Producto.objects.filter(
            disponible=True,
            categoria__activo=True
        ).select_related(
            'categoria'
        ).prefetch_related(
            Prefetch(
                'variantes',
                queryset=variantes_activas,
                to_attr='variantes_menu'
            ),
            Prefetch(
                'extras_permitidos',
                queryset=extras_permitidos,
                to_attr='extras_menu'
            )
        ).order_by('nombre')

        # ==========================================
        # SERIALIZAR PRODUCTOS ORIGINALES
        # ==========================================

        lista_productos = []

        for producto in productos:

            # Conservamos todos los campos actuales
            # del serializador de productos.
            datos_producto = ProductoSerializer(
                producto,
                context={'request': request}
            ).data

            # ======================================
            # AGREGAR VARIANTES
            # ======================================

            variantes = []

            for variante in producto.variantes_menu:

                variantes.append({
                    'id': variante.id,
                    'nombre': variante.nombre,
                    'precio': str(variante.precio),
                    'orden': variante.orden,
                    'activo': variante.activo
                })

            # ======================================
            # AGREGAR EXTRAS PERMITIDOS
            # ======================================

            extras = []

            for permiso in producto.extras_menu:

                extra = permiso.extra

                extras.append({
                    'id': extra.id,
                    'nombre': extra.nombre,
                    'descripcion': extra.descripcion,
                    'precio': str(extra.precio),
                    'obligatorio': permiso.obligatorio,
                    'cantidad_maxima': permiso.cantidad_maxima,
                    'activo': permiso.activo
                })

            # ======================================
            # INCORPORAR PERSONALIZACIONES
            # ======================================

            datos_producto['variantes'] = variantes
            datos_producto['extras'] = extras

            lista_productos.append(datos_producto)

        # ==========================================
        # RESPUESTA PÚBLICA
        # ==========================================

        return Response({
            'categorias': CategoriaSerializer(
                categorias,
                many=True
            ).data,
            'productos': lista_productos
        })
