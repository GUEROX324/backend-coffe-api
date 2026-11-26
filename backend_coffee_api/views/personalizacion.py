
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend_coffee_api.models import VarianteProducto, Ingrediente, RecetaDetalle, Extra, ExtraPermitido
from backend_coffee_api.permissions import EsAdministrador
from backend_coffee_api.serializers import VarianteProductoSerializer, IngredienteSerializer, RecetaDetalleSerializer, ExtraSerializer, ExtraPermitidoSerializer


# =====================================================
# VISTA BASE PARA LISTAR Y CREAR REGISTROS
# =====================================================

class CatalogoPersonalizacionBase(APIView):
    permission_classes = [EsAdministrador]

    modelo = None
    serializer_class = None
    filtros_permitidos = ()

    def obtener_queryset(self, request):
        queryset = self.modelo.objects.all().order_by('id')
        filtros = {}

        for campo in self.filtros_permitidos:
            valor = request.query_params.get(campo)

            if valor is not None and valor != '':
                if not valor.isdigit() or int(valor) < 1:
                    return None

                filtros[campo] = int(valor)

        return queryset.filter(**filtros)

    # =====================================================
    # LISTAR REGISTROS
    # =====================================================

    def get(self, request):
        queryset = self.obtener_queryset(request)

        if queryset is None:
            return Response(
                {'message': 'El filtro proporcionado no es válido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)

    # =====================================================
    # CREAR REGISTRO
    # =====================================================

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                instancia = serializer.save()

        except IntegrityError:
            return Response(
                {
                    'message': 'No se pudo crear el registro porque los datos incumplen una restricción de integridad.'
                },
                status=status.HTTP_409_CONFLICT
            )

        return Response(
            {
                'message': 'Registro creado correctamente.',
                'registro': self.serializer_class(instancia).data
            },
            status=status.HTTP_201_CREATED
        )


# =====================================================
# VISTA BASE PARA CONSULTAR, EDITAR Y ELIMINAR
# =====================================================

class CatalogoPersonalizacionDetalleBase(APIView):
    permission_classes = [EsAdministrador]

    modelo = None
    serializer_class = None

    # =====================================================
    # CONSULTAR REGISTRO POR ID
    # =====================================================

    def get(self, request, id):
        instancia = get_object_or_404(self.modelo, pk=id)

        return Response({
            'registro': self.serializer_class(instancia).data
        })

    # =====================================================
    # ACTUALIZAR REGISTRO
    # =====================================================

    def patch(self, request, id):
        instancia = get_object_or_404(self.modelo, pk=id)

        serializer = self.serializer_class(
            instancia,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                instancia = serializer.save()

        except IntegrityError:
            return Response(
                {
                    'message': 'No se pudo actualizar el registro porque existe un conflicto de integridad.'
                },
                status=status.HTTP_409_CONFLICT
            )

        return Response({
            'message': 'Registro actualizado correctamente.',
            'registro': self.serializer_class(instancia).data
        })

    # =====================================================
    # ELIMINAR REGISTRO
    # =====================================================

    def delete(self, request, id):
        instancia = get_object_or_404(self.modelo, pk=id)

        try:
            with transaction.atomic():
                instancia.delete()

        except (ProtectedError, RestrictedError, IntegrityError):
            return Response(
                {
                    'message': 'No es posible eliminar este registro porque tiene información relacionada. Puedes desactivarlo cuando corresponda.'
                },
                status=status.HTTP_409_CONFLICT
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================
# VARIANTES DE PRODUCTOS
# =====================================================

class VariantesView(CatalogoPersonalizacionBase):
    modelo = VarianteProducto
    serializer_class = VarianteProductoSerializer
    filtros_permitidos = ('producto_id',)


class VarianteDetalleView(CatalogoPersonalizacionDetalleBase):
    modelo = VarianteProducto
    serializer_class = VarianteProductoSerializer


# =====================================================
# INGREDIENTES
# =====================================================

class IngredientesView(CatalogoPersonalizacionBase):
    modelo = Ingrediente
    serializer_class = IngredienteSerializer


class IngredienteDetalleView(CatalogoPersonalizacionDetalleBase):
    modelo = Ingrediente
    serializer_class = IngredienteSerializer


# =====================================================
# RECETAS POR VARIANTE
# =====================================================

class RecetasView(CatalogoPersonalizacionBase):
    modelo = RecetaDetalle
    serializer_class = RecetaDetalleSerializer
    filtros_permitidos = ('variante_id',)


class RecetaDetalleView(CatalogoPersonalizacionDetalleBase):
    modelo = RecetaDetalle
    serializer_class = RecetaDetalleSerializer


# =====================================================
# EXTRAS
# =====================================================

class ExtrasView(CatalogoPersonalizacionBase):
    modelo = Extra
    serializer_class = ExtraSerializer


class ExtraDetalleView(CatalogoPersonalizacionDetalleBase):
    modelo = Extra
    serializer_class = ExtraSerializer


# =====================================================
# EXTRAS PERMITIDOS POR PRODUCTO
# =====================================================

class ExtrasPermitidosView(CatalogoPersonalizacionBase):
    modelo = ExtraPermitido
    serializer_class = ExtraPermitidoSerializer
    filtros_permitidos = ('producto_id',)


class ExtraPermitidoDetalleView(CatalogoPersonalizacionDetalleBase):
    modelo = ExtraPermitido
    serializer_class = ExtraPermitidoSerializer
