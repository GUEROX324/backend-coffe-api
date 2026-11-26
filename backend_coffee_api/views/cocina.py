
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from backend_coffee_api.models import Pedido, DetallePedido, Preparacion
from backend_coffee_api.permissions import EsCocinero
from backend_coffee_api.serializers import PedidoCocinaSerializer, PreparacionSerializer, ActualizarPreparacionSerializer


def obtener_pedidos_cocina():
    preparaciones = Preparacion.objects.select_related('responsable').order_by('id')
    detalles = DetallePedido.objects.prefetch_related(Prefetch('preparaciones', queryset=preparaciones)).order_by('id')

    return Pedido.objects.filter(
        pago_confirmado=True,
        estado__in=[Pedido.Estado.PENDIENTE, Pedido.Estado.PREPARACION, Pedido.Estado.LISTO]
    ).prefetch_related(Prefetch('detalles', queryset=detalles)).order_by('fecha', 'id')


class PedidosCocinaView(APIView):
    permission_classes = [EsCocinero]

    def get(self, request):
        pedidos = obtener_pedidos_cocina()
        estado = request.query_params.get('estado')

        if estado:
            estados_validos = [Pedido.Estado.PENDIENTE, Pedido.Estado.PREPARACION, Pedido.Estado.LISTO]

            if estado not in estados_validos:
                return Response({'message': 'Estado de pedido no válido.'}, status=status.HTTP_400_BAD_REQUEST)

            pedidos = pedidos.filter(estado=estado)

        paginador = PageNumberPagination()
        pagina = paginador.paginate_queryset(pedidos, request, view=self)

        return paginador.get_paginated_response(PedidoCocinaSerializer(pagina, many=True).data)


class PedidoCocinaDetalleView(APIView):
    permission_classes = [EsCocinero]

    def get(self, request, id):
        pedido = get_object_or_404(obtener_pedidos_cocina(), pk=id)

        return Response({
            'pedido': PedidoCocinaSerializer(pedido).data
        })


class ActualizarPreparacionView(APIView):
    permission_classes = [EsCocinero]

    def patch(self, request, id):
        serializer = ActualizarPreparacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        accion = serializer.validated_data['accion']

        with transaction.atomic():
            pedido_id = Preparacion.objects.filter(pk=id).values_list('detalle__pedido_id', flat=True).first()
            if pedido_id is None:
                return Response({'message': 'La preparación no existe.'}, status=status.HTTP_404_NOT_FOUND)

            pedido = get_object_or_404(Pedido.objects.select_for_update(), pk=pedido_id)
            preparacion = get_object_or_404(
                Preparacion.objects.select_for_update().select_related('detalle', 'responsable'),
                pk=id,
                detalle__pedido_id=pedido.id
            )

            if not pedido.pago_confirmado or pedido.estado in [Pedido.Estado.CANCELADO, Pedido.Estado.ENTREGADO]:
                return Response({'message': 'Este pedido no permite modificar preparaciones.'}, status=status.HTTP_409_CONFLICT)

            if accion == 'iniciar':
                if preparacion.estado != Preparacion.Estado.PENDIENTE:
                    return Response({'message': 'Solo puedes iniciar una preparación pendiente.'}, status=status.HTTP_409_CONFLICT)

                preparacion.estado = Preparacion.Estado.PREPARACION
                preparacion.responsable = request.user
                preparacion.fecha_inicio = timezone.now()
                preparacion.save(update_fields=['estado', 'responsable', 'fecha_inicio'])

            elif accion == 'finalizar':
                if preparacion.estado != Preparacion.Estado.PREPARACION:
                    return Response({'message': 'Primero debes iniciar la preparación.'}, status=status.HTTP_409_CONFLICT)

                if preparacion.responsable_id != request.user.id:
                    return Response({'message': 'Esta preparación está asignada a otro cocinero.'}, status=status.HTTP_403_FORBIDDEN)

                preparacion.estado = Preparacion.Estado.LISTO
                preparacion.fecha_fin = timezone.now()
                preparacion.save(update_fields=['estado', 'fecha_fin'])

            preparaciones = Preparacion.objects.filter(detalle__pedido=pedido)
            total_unidades = preparaciones.count()
            unidades_listas = preparaciones.filter(estado=Preparacion.Estado.LISTO).count()
            unidades_iniciadas = preparaciones.exclude(estado=Preparacion.Estado.PENDIENTE).count()

            if total_unidades > 0 and unidades_listas == total_unidades:
                pedido.estado = Pedido.Estado.LISTO
            elif unidades_iniciadas > 0:
                pedido.estado = Pedido.Estado.PREPARACION
            else:
                pedido.estado = Pedido.Estado.PENDIENTE

            pedido.save(update_fields=['estado', 'update'])

        return Response({
            'message': 'Preparación actualizada correctamente.',
            'preparacion': PreparacionSerializer(preparacion).data,
            'pedido': {
                'id': pedido.id,
                'estado': pedido.estado,
                'total_unidades': total_unidades,
                'unidades_listas': unidades_listas
            }
        }, status=status.HTTP_200_OK)