
from rest_framework.permissions import BasePermission


class EsAdministrador(BasePermission):
    message = 'No tienes permisos de administrador.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.groups.filter(name='admin').exists()


class EsColaborador(BasePermission):
    message = 'No tienes permisos de colaborador.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.groups.filter(name='colaborador').exists()


class EsCocinero(BasePermission):
    message = 'No tienes permisos de cocinero.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.groups.filter(name='cocinero').exists()

class EsAdministradorOColaborador(BasePermission):
    message = 'No tienes permisos para consultar pedidos.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated or not request.user.is_active:
            return False

        return request.user.groups.filter(name__in=['admin', 'colaborador']).exists()