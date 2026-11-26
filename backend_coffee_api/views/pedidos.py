
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from backend_coffee_api.models import Producto, Pedido, DetallePedido, Preparacion, TurnoCaja, VentaCaja
from backend_coffee_api.serializers import CrearPedidoSerializer, PedidoSerializer
from backend_coffee_api.permissions import EsColaborador, EsAdministradorOColaborador


class PedidosView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [EsColaborador()]

        return [EsAdministradorOColaborador()]

    def get(self, request):
        pedidos = Pedido.objects.select_related('cajero').prefetch_related('detalles').order_by('-fecha', '-id')

        if not request.user.groups.filter(name='admin').exists():
            pedidos = pedidos.filter(cajero=request.user)

        estado = request.query_params.get('estado')
        metodo_pago = request.query_params.get('metodo_pago')

        if estado:
            if estado not in Pedido.Estado.values:
                return Response({'message': 'Estado de pedido no válido.'}, status=status.HTTP_400_BAD_REQUEST)

            pedidos = pedidos.filter(estado=estado)

        if metodo_pago:
            if metodo_pago not in Pedido.MetodoPago.values:
                return Response({'message': 'Método de pago no válido.'}, status=status.HTTP_400_BAD_REQUEST)

            pedidos = pedidos.filter(metodo_pago=metodo_pago)

        paginador = PageNumberPagination()
        pagina = paginador.paginate_queryset(pedidos, request, view=self)

        return paginador.get_paginated_response(PedidoSerializer(pagina, many=True).data)

    def post(self, request):
        serializer = CrearPedidoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        with transaction.atomic():
            turno = TurnoCaja.objects.select_for_update().filter(estado=TurnoCaja.Estado.ABIERTA).first()

            if turno is None:
                return Response({'message': 'Debes abrir la caja antes de registrar pedidos.'}, status=status.HTTP_409_CONFLICT)

            if turno.colaborador_id != request.user.id:
                return Response({'message': 'Solo el colaborador responsable del turno puede registrar ventas.'}, status=status.HTTP_403_FORBIDDEN)

            ids = [detalle['producto'] for detalle in datos['detalles']]
            productos = Producto.objects.select_for_update().select_related('categoria').filter(id__in=ids).order_by('id')
            productos = {producto.id: producto for producto in productos}

            if len(productos) != len(ids):
                return Response({'message': 'Uno o más productos no existen.'}, status=status.HTTP_400_BAD_REQUEST)

            total = Decimal('0.00')
            detalles_calculados = []

            for item in datos['detalles']:
                producto = productos[item['producto']]

                if not producto.disponible or not producto.categoria.activo:
                    return Response({'message': f'El producto {producto.nombre} no está disponible.'}, status=status.HTTP_400_BAD_REQUEST)

                subtotal = producto.precio * item['cantidad']
                total += subtotal

                detalles_calculados.append({
                    'producto': producto,
                    'cantidad': item['cantidad'],
                    'precio': producto.precio,
                    'subtotal': subtotal
                })

            if total <= 0:
                return Response({'message': 'El total del pedido debe ser mayor que cero.'}, status=status.HTTP_400_BAD_REQUEST)

            metodo_pago = datos['metodo_pago']
            efectivo_recibido = None
            cambio = Decimal('0.00')

            if metodo_pago == Pedido.MetodoPago.EFECTIVO:
                efectivo_recibido = datos['efectivo_recibido']

                if efectivo_recibido < total:
                    return Response({'message': 'El efectivo recibido es insuficiente.'}, status=status.HTTP_400_BAD_REQUEST)

                cambio = efectivo_recibido - total

            pedido = Pedido.objects.create(
                cajero=request.user,
                total=total,
                metodo_pago=metodo_pago,
                pago_confirmado=True,
                efectivo_recibido=efectivo_recibido,
                cambio=cambio,
                estado=Pedido.Estado.PENDIENTE
            )

            for item in detalles_calculados:
                detalle = DetallePedido.objects.create(
                    pedido=pedido,
                    producto=item['producto'],
                    nombre_producto=item['producto'].nombre,
                    precio_unitario=item['precio'],
                    cantidad=item['cantidad'],
                    subtotal=item['subtotal']
                )

                Preparacion.objects.bulk_create([
                    Preparacion(detalle=detalle, numero_unidad=numero)
                    for numero in range(1, item['cantidad'] + 1)
                ])

            VentaCaja.objects.create(turno=turno, pedido=pedido)

        return Response({
            'message': 'Pedido registrado correctamente.',
            'pedido': PedidoSerializer(pedido).data
        }, status=status.HTTP_201_CREATED)


class PedidoDetalleView(APIView):
    permission_classes = [EsAdministradorOColaborador]

    def get(self, request, id):
        pedidos = Pedido.objects.select_related('cajero').prefetch_related('detalles')

        if not request.user.groups.filter(name='admin').exists():
            pedidos = pedidos.filter(cajero=request.user)

        pedido = get_object_or_404(pedidos, pk=id)

        return Response({
            'pedido': PedidoSerializer(pedido).data
        })
