
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Count, Q, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from backend_coffee_api.models import ConfiguracionSistema, TurnoCaja, MovimientoCaja, VentaCaja, Pedido
from backend_coffee_api.permissions import EsColaborador, EsAdministradorOColaborador
from backend_coffee_api.serializers import AperturaCajaSerializer, TurnoCajaSerializer, RegistrarMovimientoCajaSerializer, MovimientoCajaSerializer, CerrarCajaSerializer, VentaCajaSerializer


DINERO = DecimalField(max_digits=12, decimal_places=2)


def calcular_resumen(turno):
    ventas = VentaCaja.objects.filter(turno=turno, pedido__pago_confirmado=True)

    resumen_ventas = ventas.aggregate(
        cantidad_ventas=Count('id'),
        ventas_efectivo=Coalesce(Sum('pedido__total', filter=Q(pedido__metodo_pago=Pedido.MetodoPago.EFECTIVO)), Decimal('0.00'), output_field=DINERO),
        ventas_terminal=Coalesce(Sum('pedido__total', filter=Q(pedido__metodo_pago=Pedido.MetodoPago.TERMINAL)), Decimal('0.00'), output_field=DINERO)
    )

    movimientos = MovimientoCaja.objects.filter(turno=turno)

    resumen_movimientos = movimientos.aggregate(
        entradas=Coalesce(Sum('monto', filter=Q(tipo=MovimientoCaja.Tipo.ENTRADA)), Decimal('0.00'), output_field=DINERO),
        retiros=Coalesce(Sum('monto', filter=Q(tipo=MovimientoCaja.Tipo.RETIRO)), Decimal('0.00'), output_field=DINERO)
    )

    ventas_efectivo = resumen_ventas['ventas_efectivo']
    ventas_terminal = resumen_ventas['ventas_terminal']
    entradas = resumen_movimientos['entradas']
    retiros = resumen_movimientos['retiros']
    efectivo_esperado = turno.fondo_inicial + ventas_efectivo + entradas - retiros

    return {
        'cantidad_ventas': resumen_ventas['cantidad_ventas'],
        'ventas_efectivo': ventas_efectivo,
        'ventas_terminal': ventas_terminal,
        'ventas_totales': ventas_efectivo + ventas_terminal,
        'entradas': entradas,
        'retiros': retiros,
        'efectivo_esperado': efectivo_esperado
    }


def obtener_turno_abierto():
    return TurnoCaja.objects.filter(estado=TurnoCaja.Estado.ABIERTA).select_related('colaborador').first()


class AbrirCajaView(APIView):
    permission_classes = [EsColaborador]

    def post(self, request):
        serializer = AperturaCajaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            ConfiguracionSistema.objects.select_for_update().get(pk=1)

            if TurnoCaja.objects.filter(estado=TurnoCaja.Estado.ABIERTA).exists():
                return Response({'message': 'Ya existe una caja abierta.'}, status=status.HTTP_409_CONFLICT)

            turno = TurnoCaja.objects.create(
                colaborador=request.user,
                fondo_inicial=serializer.validated_data['fondo_inicial'],
                estado=TurnoCaja.Estado.ABIERTA
            )

        return Response({
            'message': 'Caja abierta correctamente.',
            'turno': TurnoCajaSerializer(turno).data
        }, status=status.HTTP_201_CREATED)


class TurnoActivoView(APIView):
    permission_classes = [EsColaborador]

    def get(self, request):
        turno = obtener_turno_abierto()

        if turno is None:
            return Response({'turno': None, 'message': 'No hay ninguna caja abierta.'})

        return Response({
            'turno': TurnoCajaSerializer(turno).data,
            'es_responsable': turno.colaborador_id == request.user.id
        })


class CajaResumenView(APIView):
    permission_classes = [EsAdministradorOColaborador]

    def get(self, request):
        turno = obtener_turno_abierto()

        if turno is None:
            return Response({'message': 'No hay ningún turno abierto.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'turno': TurnoCajaSerializer(turno).data,
            'resumen': calcular_resumen(turno)
        })


class MovimientosCajaView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [EsColaborador()]

        return [EsAdministradorOColaborador()]

    def get(self, request):
        turno = obtener_turno_abierto()

        if turno is None:
            return Response({'message': 'No hay ningún turno abierto.'}, status=status.HTTP_404_NOT_FOUND)

        movimientos = MovimientoCaja.objects.filter(turno=turno).select_related('colaborador').order_by('-fecha', '-id')

        paginador = PageNumberPagination()
        pagina = paginador.paginate_queryset(movimientos, request, view=self)

        return paginador.get_paginated_response(MovimientoCajaSerializer(pagina, many=True).data)

    def post(self, request):
        serializer = RegistrarMovimientoCajaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        with transaction.atomic():
            turno = TurnoCaja.objects.select_for_update().filter(estado=TurnoCaja.Estado.ABIERTA).first()

            if turno is None:
                return Response({'message': 'Debes abrir la caja antes de registrar movimientos.'}, status=status.HTTP_409_CONFLICT)

            if turno.colaborador_id != request.user.id:
                return Response({'message': 'Solo el responsable del turno puede registrar movimientos.'}, status=status.HTTP_403_FORBIDDEN)

            if datos['tipo'] == MovimientoCaja.Tipo.RETIRO:
                resumen = calcular_resumen(turno)

                if datos['monto'] > resumen['efectivo_esperado']:
                    return Response({'message': 'No puedes retirar más efectivo del disponible en caja.'}, status=status.HTTP_400_BAD_REQUEST)

            movimiento = MovimientoCaja.objects.create(
                turno=turno,
                colaborador=request.user,
                tipo=datos['tipo'],
                monto=datos['monto'],
                motivo=datos['motivo']
            )

        return Response({
            'message': 'Movimiento registrado correctamente.',
            'movimiento': MovimientoCajaSerializer(movimiento).data
        }, status=status.HTTP_201_CREATED)


class CerrarCajaView(APIView):
    permission_classes = [EsColaborador]

    def post(self, request):
        serializer = CerrarCajaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            turno = TurnoCaja.objects.select_for_update().filter(estado=TurnoCaja.Estado.ABIERTA).first()

            if turno is None:
                return Response({'message': 'No hay un turno abierto para cerrar.'}, status=status.HTTP_409_CONFLICT)

            if turno.colaborador_id != request.user.id:
                return Response({'message': 'Solo el responsable del turno puede cerrarlo.'}, status=status.HTTP_403_FORBIDDEN)

            resumen = calcular_resumen(turno)
            declarado = serializer.validated_data['efectivo_declarado']
            esperado = resumen['efectivo_esperado']

            turno.efectivo_esperado_cierre = esperado
            turno.efectivo_declarado = declarado
            turno.diferencia = declarado - esperado
            turno.cierre = timezone.now()
            turno.estado = TurnoCaja.Estado.CERRADA
            turno.save(update_fields=[
                'efectivo_esperado_cierre',
                'efectivo_declarado',
                'diferencia',
                'cierre',
                'estado'
            ])

        return Response({
            'message': 'Caja cerrada correctamente.',
            'turno': TurnoCajaSerializer(turno).data,
            'resumen': resumen
        }, status=status.HTTP_200_OK)


class HistorialCajaView(APIView):
    permission_classes = [EsAdministradorOColaborador]

    def get(self, request):
        turnos = TurnoCaja.objects.select_related('colaborador').order_by('-apertura', '-id')

        if not request.user.groups.filter(name='admin').exists():
            turnos = turnos.filter(colaborador=request.user)

        estado = request.query_params.get('estado')

        if estado:
            if estado not in TurnoCaja.Estado.values:
                return Response({'message': 'Estado de turno no válido.'}, status=status.HTTP_400_BAD_REQUEST)

            turnos = turnos.filter(estado=estado)

        paginador = PageNumberPagination()
        pagina = paginador.paginate_queryset(turnos, request, view=self)

        return paginador.get_paginated_response(TurnoCajaSerializer(pagina, many=True).data)


# =====================================================
# DETALLE HISTÓRICO DE UN TURNO DE CAJA
# =====================================================

class DetalleHistorialCajaView(APIView):
    permission_classes = [EsAdministradorOColaborador]

    def get(self, request, turno_id):
        turnos = TurnoCaja.objects.select_related('colaborador')

        # Los administradores pueden consultar todos los turnos.
        # Los colaboradores solo pueden consultar sus propios turnos.
        if not request.user.groups.filter(name='admin').exists():
            turnos = turnos.filter(colaborador=request.user)

        turno = get_object_or_404(turnos, pk=turno_id)

        if turno.estado != TurnoCaja.Estado.CERRADA:
            return Response(
                {
                    'message': 'Este turno todavía no está cerrado.'
                },
                status=status.HTTP_409_CONFLICT
            )

        ventas = (
            VentaCaja.objects
            .filter(
                turno=turno,
                pedido__pago_confirmado=True
            )
            .select_related('pedido')
            .order_by('fecha', 'id')
        )

        movimientos = (
            MovimientoCaja.objects
            .filter(turno=turno)
            .select_related('colaborador')
            .order_by('fecha', 'id')
        )

        return Response({
            'turno': TurnoCajaSerializer(turno).data,
            'resumen': calcular_resumen(turno),
            'ventas': VentaCajaSerializer(
                ventas,
                many=True
            ).data,
            'movimientos': MovimientoCajaSerializer(
                movimientos,
                many=True
            ).data
        })
