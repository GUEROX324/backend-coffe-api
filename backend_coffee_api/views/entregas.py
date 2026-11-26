
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from backend_coffee_api.models import Pedido, Preparacion, Entrega
from backend_coffee_api.permissions import EsColaborador, EsAdministradorOColaborador
from backend_coffee_api.serializers import PedidoSerializer, RegistrarEntregaSerializer, EntregaSerializer


class PedidosListosView(APIView):
    permission_classes = [EsColaborador]

    def get(self, request):
        pedidos = Pedido.objects.filter(
            estado=Pedido.Estado.LISTO,
            pago_confirmado=True,
            entrega__isnull=True
        ).select_related('cajero').prefetch_related('detalles').order_by('fecha', 'id')

        paginador = PageNumberPagination()
        pagina = paginador.paginate_queryset(pedidos, request, view=self)

        return paginador.get_paginated_response(PedidoSerializer(pagina, many=True).data)


class EntregasView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [EsColaborador()]

        return [EsAdministradorOColaborador()]

    def get(self, request):
        entregas = Entrega.objects.select_related('pedido', 'responsable').prefetch_related('pedido__detalles').order_by('-fecha', '-id')

        if not request.user.groups.filter(name='admin').exists():
            entregas = entregas.filter(responsable=request.user)

        busqueda = request.query_params.get('q', '').strip()

        if busqueda:
            entregas = entregas.filter(
                Q(responsable__username__icontains=busqueda) |
                Q(pedido__cajero__username__icontains=busqueda)
            )

        paginador = PageNumberPagination()
        pagina = paginador.paginate_queryset(entregas, request, view=self)

        return paginador.get_paginated_response(EntregaSerializer(pagina, many=True).data)

    def post(self, request):
        serializer = RegistrarEntregaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        with transaction.atomic():
            pedido = get_object_or_404(
                Pedido.objects.select_for_update(),
                pk=datos['pedido']
            )

            if Entrega.objects.filter(pedido=pedido).exists():
                return Response({'message': 'Este pedido ya fue entregado.'}, status=status.HTTP_409_CONFLICT)

            if pedido.estado != Pedido.Estado.LISTO:
                return Response({'message': 'El pedido todavía no está listo para entregar.'}, status=status.HTTP_409_CONFLICT)

            if not pedido.pago_confirmado:
                return Response({'message': 'No puedes entregar un pedido sin pago confirmado.'}, status=status.HTTP_409_CONFLICT)

            resumen = Preparacion.objects.filter(detalle__pedido=pedido).aggregate(
                total=Count('id'),
                pendientes=Count('id', filter=~Q(estado=Preparacion.Estado.LISTO))
            )

            if resumen['total'] == 0 or resumen['pendientes'] > 0:
                return Response({'message': 'El pedido tiene preparaciones pendientes.'}, status=status.HTTP_409_CONFLICT)

            entrega = Entrega.objects.create(
                pedido=pedido,
                responsable=request.user,
                observaciones=datos.get('observaciones', '')
            )

            pedido.estado = Pedido.Estado.ENTREGADO
            pedido.save(update_fields=['estado', 'update'])

        return Response({
            'message': 'Pedido entregado correctamente.',
            'entrega': EntregaSerializer(entrega).data
        }, status=status.HTTP_201_CREATED)


class EntregaDetalleView(APIView):
    permission_classes = [EsAdministradorOColaborador]

    def get(self, request, id):
        entregas = Entrega.objects.select_related('pedido', 'responsable').prefetch_related('pedido__detalles')

        if not request.user.groups.filter(name='admin').exists():
            entregas = entregas.filter(responsable=request.user)

        entrega = get_object_or_404(entregas, pk=id)

        return Response({
            'entrega': EntregaSerializer(entrega).data
        })
