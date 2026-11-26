
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import (
    JSONParser,
    MultiPartParser,
    FormParser
)

from backend_coffee_api.models import Producto, DetallePedido
from backend_coffee_api.serializers import ProductoSerializer
from backend_coffee_api.permissions import (
    EsAdministrador,
    EsAdministradorOColaborador
)


# =====================================================
# LISTADO Y REGISTRO DE PRODUCTOS
# =====================================================

class ProductosView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [EsAdministradorOColaborador()]

        return [EsAdministrador()]

    def get(self, request):
        productos = Producto.objects.select_related(
            'categoria'
        ).all().order_by('id')

        categoria = request.query_params.get('categoria')
        disponible = request.query_params.get('disponible')
        busqueda = request.query_params.get('q', '').strip()

        if categoria:
            if not categoria.isdigit():
                return Response(
                    {'message': 'El ID de categoría no es válido.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            productos = productos.filter(
                categoria_id=int(categoria)
            )

        if disponible is not None:
            if disponible.lower() not in ['true', 'false']:
                return Response(
                    {'message': 'El estado debe ser true o false.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            productos = productos.filter(
                disponible=disponible.lower() == 'true'
            )

        if busqueda:
            productos = productos.filter(
                nombre__icontains=busqueda
            )

        paginador = PageNumberPagination()

        pagina = paginador.paginate_queryset(
            productos,
            request,
            view=self
        )

        serializer = ProductoSerializer(
            pagina,
            many=True,
            context={'request': request}
        )

        return paginador.get_paginated_response(
            serializer.data
        )

    def post(self, request):
        serializer = ProductoSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        producto = serializer.save()

        return Response({
            'message': 'Producto registrado correctamente.',
            'producto': ProductoSerializer(
                producto,
                context={'request': request}
            ).data
        }, status=status.HTTP_201_CREATED)


# =====================================================
# CONSULTA, ACTUALIZACIÓN Y ELIMINACIÓN
# =====================================================

class ProductoDetalleView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [EsAdministradorOColaborador()]

        return [EsAdministrador()]

    def get(self, request, id):
        producto = get_object_or_404(
            Producto.objects.select_related('categoria'),
            pk=id
        )

        serializer = ProductoSerializer(
            producto,
            context={'request': request}
        )

        return Response({
            'producto': serializer.data
        })

    def patch(self, request, id):
        producto = get_object_or_404(
            Producto.objects.select_related('categoria'),
            pk=id
        )

        serializer = ProductoSerializer(
            producto,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Producto actualizado correctamente.',
            'producto': serializer.data
        }, status=status.HTTP_200_OK)

    # ==========================================
    # ELIMINAR PRODUCTO
    # ==========================================

    def delete(self, request, id):
        try:
            with transaction.atomic():
                producto = get_object_or_404(
                    Producto.objects.select_for_update(),
                    pk=id
                )

                # No eliminar un producto vendido:
                # debe preservarse el historial.
                if DetallePedido.objects.filter(
                    producto_id=producto.id
                ).exists():
                    return Response(
                        {
                            'message': (
                                'Este producto tiene pedidos '
                                'registrados y no puede eliminarse. '
                                'Puedes desactivarlo para que deje '
                                'de estar disponible para la venta.'
                            )
                        },
                        status=status.HTTP_409_CONFLICT
                    )

                producto.delete()

        except (ProtectedError, RestrictedError, IntegrityError):
            return Response(
                {
                    'message': (
                        'No es posible eliminar este producto '
                        'porque existen registros relacionados. '
                        'Puedes desactivarlo en su lugar.'
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )
