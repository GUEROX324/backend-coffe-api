
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Q, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response

from backend_coffee_api.models import (
    Pedido,
    DetallePedido,
    VentaCaja,
    TurnoCaja
)

from backend_coffee_api.permissions import EsAdministrador
from backend_coffee_api.serializers import FiltroReporteSerializer


DINERO = DecimalField(max_digits=14, decimal_places=2)
CERO = Decimal('0.00')


# ==========================================
# FILTROS Y PERIODOS
# ==========================================

def obtener_fechas(request):
    serializer = FiltroReporteSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def obtener_intervalo(fechas):
    zona = timezone.get_current_timezone()

    inicio = timezone.make_aware(
        datetime.combine(fechas['fecha_inicio'], time.min),
        timezone=zona
    )

    fin = timezone.make_aware(
        datetime.combine(
            fechas['fecha_fin'] + timedelta(days=1),
            time.min
        ),
        timezone=zona
    )

    return inicio, fin


def datos_periodo(fechas):
    return {
        'fecha_inicio': fechas['fecha_inicio'].isoformat(),
        'fecha_fin': fechas['fecha_fin'].isoformat()
    }


# ==========================================
# CONSULTAS BASE
# ==========================================

def obtener_ventas(fechas):
    inicio, fin = obtener_intervalo(fechas)

    return VentaCaja.objects.filter(
        pedido__pago_confirmado=True,
        pedido__fecha__gte=inicio,
        pedido__fecha__lt=fin
    )


def obtener_pedidos(fechas):
    inicio, fin = obtener_intervalo(fechas)

    return Pedido.objects.filter(
        fecha__gte=inicio,
        fecha__lt=fin
    )


def obtener_turnos_cerrados(fechas):
    inicio, fin = obtener_intervalo(fechas)

    return TurnoCaja.objects.filter(
        estado=TurnoCaja.Estado.CERRADA,
        cierre__gte=inicio,
        cierre__lt=fin
    )


# ==========================================
# ESTADÍSTICAS: RESUMEN
# ==========================================

class StatsResumenView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request):
        fechas = obtener_fechas(request)
        ventas = obtener_ventas(fechas)

        resumen = ventas.aggregate(
            cantidad_ventas=Count('id'),

            ingresos_efectivo=Coalesce(
                Sum(
                    'pedido__total',
                    filter=Q(
                        pedido__metodo_pago=Pedido.MetodoPago.EFECTIVO
                    )
                ),
                CERO,
                output_field=DINERO
            ),

            ingresos_terminal=Coalesce(
                Sum(
                    'pedido__total',
                    filter=Q(
                        pedido__metodo_pago=Pedido.MetodoPago.TERMINAL
                    )
                ),
                CERO,
                output_field=DINERO
            )
        )

        ingresos_totales = (
            resumen['ingresos_efectivo'] +
            resumen['ingresos_terminal']
        )

        promedio = (
            ingresos_totales / resumen['cantidad_ventas']
            if resumen['cantidad_ventas']
            else CERO
        )

        return Response({
            'periodo': datos_periodo(fechas),
            'cantidad_ventas': resumen['cantidad_ventas'],
            'ingresos_efectivo': resumen['ingresos_efectivo'],
            'ingresos_terminal': resumen['ingresos_terminal'],
            'ingresos_totales': ingresos_totales,
            'ticket_promedio': round(promedio, 2)
        })


# ==========================================
# ESTADÍSTICAS: VENTAS POR DÍA
# ==========================================

class StatsVentasView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request):
        fechas = obtener_fechas(request)

        ventas = obtener_ventas(fechas).select_related('pedido')

        agrupadas = {}

        for venta in ventas.iterator():
            pedido = venta.pedido

            fecha_local = timezone.localtime(
                pedido.fecha
            ).date().isoformat()

            if fecha_local not in agrupadas:
                agrupadas[fecha_local] = {
                    'fecha': fecha_local,
                    'cantidad_ventas': 0,
                    'efectivo': CERO,
                    'terminal': CERO,
                    'total': CERO
                }

            registro = agrupadas[fecha_local]
            registro['cantidad_ventas'] += 1

            if pedido.metodo_pago == Pedido.MetodoPago.EFECTIVO:
                registro['efectivo'] += pedido.total

            elif pedido.metodo_pago == Pedido.MetodoPago.TERMINAL:
                registro['terminal'] += pedido.total

            registro['total'] = (
                registro['efectivo'] +
                registro['terminal']
            )

        resultados = [
            agrupadas[fecha]
            for fecha in sorted(agrupadas)
        ]

        return Response({
            'periodo': datos_periodo(fechas),
            'ventas': resultados
        })


# ==========================================
# ESTADÍSTICAS: PRODUCTOS
# ==========================================

class StatsProductosView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request):
        fechas = obtener_fechas(request)
        inicio, fin = obtener_intervalo(fechas)

        productos = DetallePedido.objects.filter(
            pedido__pago_confirmado=True,
            pedido_id__in=VentaCaja.objects.values('pedido_id'),
            pedido__fecha__gte=inicio,
            pedido__fecha__lt=fin
        ).values(
            'producto_id',
            'nombre_producto'
        ).annotate(
            unidades_vendidas=Coalesce(
                Sum('cantidad'),
                0
            ),
            importe_vendido=Coalesce(
                Sum('subtotal'),
                CERO,
                output_field=DINERO
            )
        ).order_by(
            '-unidades_vendidas',
            '-importe_vendido'
        )[:10]

        return Response({
            'periodo': datos_periodo(fechas),
            'productos': list(productos)
        })


# ==========================================
# ESTADÍSTICAS: PEDIDOS POR ESTADO
# ==========================================

class StatsPedidosView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request):
        fechas = obtener_fechas(request)
        pedidos = obtener_pedidos(fechas)

        agrupados = pedidos.values('estado').annotate(
            cantidad=Count('id')
        ).order_by('estado')

        conteos = {
            item['estado']: item['cantidad']
            for item in agrupados
        }

        estados = [
            {
                'estado': valor,
                'nombre': nombre,
                'cantidad': conteos.get(valor, 0)
            }
            for valor, nombre in Pedido.Estado.choices
        ]

        return Response({
            'periodo': datos_periodo(fechas),
            'total_pedidos': sum(
                item['cantidad']
                for item in estados
            ),
            'estados': estados
        })


# ==========================================
# ESTADÍSTICAS: CAJA
# ==========================================

class StatsCajaView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request):
        fechas = obtener_fechas(request)
        turnos = obtener_turnos_cerrados(fechas)

        resumen = turnos.aggregate(
            turnos_cerrados=Count('id'),

            efectivo_esperado=Coalesce(
                Sum('efectivo_esperado_cierre'),
                CERO,
                output_field=DINERO
            ),

            efectivo_declarado=Coalesce(
                Sum('efectivo_declarado'),
                CERO,
                output_field=DINERO
            ),

            sobrantes=Coalesce(
                Sum(
                    'diferencia',
                    filter=Q(diferencia__gt=0)
                ),
                CERO,
                output_field=DINERO
            ),

            faltantes=Coalesce(
                Sum(
                    'diferencia',
                    filter=Q(diferencia__lt=0)
                ),
                CERO,
                output_field=DINERO
            )
        )

        return Response({
            'periodo': datos_periodo(fechas),
            'turnos_cerrados': resumen['turnos_cerrados'],
            'efectivo_esperado': resumen['efectivo_esperado'],
            'efectivo_declarado': resumen['efectivo_declarado'],
            'sobrantes': resumen['sobrantes'],
            'faltantes': abs(resumen['faltantes']),
            'diferencia_neta': (
                resumen['sobrantes'] +
                resumen['faltantes']
            )
        })
