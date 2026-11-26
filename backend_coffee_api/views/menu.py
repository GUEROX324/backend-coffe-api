
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from backend_coffee_api.models import Categoria, Producto
from backend_coffee_api.serializers import CategoriaSerializer, ProductoSerializer


class MenuPublicoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        categorias = Categoria.objects.filter(activo=True).order_by('nombre')
        productos = Producto.objects.filter(disponible=True, categoria__activo=True).select_related('categoria').order_by('nombre')

        return Response({
            'categorias': CategoriaSerializer(categorias, many=True).data,
            'productos': ProductoSerializer(productos, many=True).data
        })
