
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

from backend_coffee_api.models import Categoria, Producto
from backend_coffee_api.serializers import CategoriaSerializer
from backend_coffee_api.permissions import (
    EsAdministrador,
    EsAdministradorOColaborador
)


class CategoriasView(APIView):

    def get_permissions(self):
        if self.request.method == 'GET':
            return [EsAdministradorOColaborador()]

        return [EsAdministrador()]

    def get(self, request):
        categorias = Categoria.objects.all().order_by('nombre')

        activo = request.query_params.get('activo')
        busqueda = request.query_params.get('q', '').strip()

        if activo is not None:
            if activo.lower() not in ['true', 'false']:
                return Response(
                    {'message': 'El estado debe ser true o false.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            categorias = categorias.filter(
                activo=activo.lower() == 'true'
            )

        if busqueda:
            categorias = categorias.filter(
                nombre__icontains=busqueda
            )

        paginador = PageNumberPagination()
        pagina = paginador.paginate_queryset(
            categorias,
            request,
            view=self
        )

        serializer = CategoriaSerializer(
            pagina,
            many=True
        )

        return paginador.get_paginated_response(
            serializer.data
        )

    def post(self, request):
        serializer = CategoriaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        categoria = serializer.save()

        return Response({
            'message': 'Categoría registrada correctamente.',
            'categoria': CategoriaSerializer(categoria).data
        }, status=status.HTTP_201_CREATED)


class CategoriaDetalleView(APIView):

    def get_permissions(self):
        if self.request.method == 'GET':
            return [EsAdministradorOColaborador()]

        return [EsAdministrador()]

    def get(self, request, id):
        categoria = get_object_or_404(
            Categoria,
            pk=id
        )

        return Response({
            'categoria': CategoriaSerializer(categoria).data
        })

    def patch(self, request, id):
        categoria = get_object_or_404(
            Categoria,
            pk=id
        )

        serializer = CategoriaSerializer(
            categoria,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Categoría actualizada correctamente.',
            'categoria': serializer.data
        })

    # ==========================================
    # ELIMINAR CATEGORÍA
    # ==========================================

    def delete(self, request, id):
        try:
            with transaction.atomic():
                categoria = get_object_or_404(
                    Categoria.objects.select_for_update(),
                    pk=id
                )

                if Producto.objects.filter(
                    categoria_id=categoria.id
                ).exists():
                    return Response(
                        {
                            'message': (
                                'No puedes eliminar esta categoría '
                                'porque todavía tiene productos '
                                'asociados. Elimina o reasigna '
                                'esos productos primero.'
                            )
                        },
                        status=status.HTTP_409_CONFLICT
                    )

                categoria.delete()

        except (ProtectedError, RestrictedError, IntegrityError):
            return Response(
                {
                    'message': (
                        'No es posible eliminar esta categoría '
                        'porque existen registros relacionados.'
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )
