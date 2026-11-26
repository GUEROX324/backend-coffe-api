
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.authtoken.models import Token

from backend_coffee_api.models import PerfilUsuario, ConfiguracionSistema
from backend_coffee_api.permissions import EsAdministrador
from backend_coffee_api.serializers import (
    EmpleadoSerializer,
    CrearEmpleadoSerializer,
    EditarEmpleadoSerializer
)


ROLES = ['admin', 'colaborador', 'cocinero']


class UsuariosView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request):
        usuarios = (
            User.objects.filter(groups__name__in=ROLES)
            .distinct()
            .select_related('perfil')
            .prefetch_related('groups')
            .order_by('id')
        )

        rol = request.query_params.get('rol')
        activo = request.query_params.get('activo')
        busqueda = request.query_params.get('q', '').strip()

        if rol:
            if rol not in ROLES:
                return Response(
                    {'message': 'El rol indicado no es válido.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            usuarios = usuarios.filter(groups__name=rol)

        if activo is not None:
            if activo.lower() not in ['true', 'false']:
                return Response(
                    {'message': 'El estado debe ser true o false.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            usuarios = usuarios.filter(is_active=activo.lower() == 'true')

        if busqueda:
            usuarios = usuarios.filter(
                Q(username__icontains=busqueda) |
                Q(first_name__icontains=busqueda) |
                Q(last_name__icontains=busqueda) |
                Q(email__icontains=busqueda)
            )

        paginador = PageNumberPagination()
        pagina = paginador.paginate_queryset(
            usuarios, request, view=self
        )
        serializer = EmpleadoSerializer(pagina, many=True)

        return paginador.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CrearEmpleadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        with transaction.atomic():
            configuracion = (
                ConfiguracionSistema.objects
                .select_for_update()
                .filter(pk=1)
                .first()
            )

            if (
                configuracion is None or
                not configuracion.completada or
                configuracion.administrador_principal_id is None
            ):
                return Response(
                    {'message': 'La configuración de administradores está incompleta.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            usuario = User.objects.create_user(
                username=datos['username'],
                first_name=datos['first_name'],
                last_name=datos['last_name'],
                email=datos['email'],
                password=datos['password'],
                is_active=datos.get('is_active', True),
                is_staff=False,
                is_superuser=False
            )

            grupo, _ = Group.objects.get_or_create(name=datos['rol'])
            usuario.groups.add(grupo)

            PerfilUsuario.objects.create(
                user=usuario,
                telefono=datos.get('telefono', '')
            )

        return Response({
            'message': 'Empleado registrado correctamente.',
            'usuario': EmpleadoSerializer(usuario).data
        }, status=status.HTTP_201_CREATED)


class UsuarioDetalleView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request, id):
        usuario = get_object_or_404(
            User.objects.filter(groups__name__in=ROLES)
            .distinct()
            .select_related('perfil')
            .prefetch_related('groups'),
            pk=id
        )

        return Response({
            'usuario': EmpleadoSerializer(usuario).data
        })

    def patch(self, request, id):
        with transaction.atomic():
            configuracion = (
                ConfiguracionSistema.objects
                .select_for_update()
                .filter(pk=1)
                .first()
            )

            if (
                configuracion is None or
                not configuracion.completada or
                configuracion.administrador_principal_id is None
            ):
                return Response(
                    {'message': 'La configuración de administradores está incompleta.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            usuario = get_object_or_404(
                User.objects.select_for_update(),
                pk=id
            )

            grupos_actuales = list(
                usuario.groups.values_list('name', flat=True)
            )

            if (
                len(grupos_actuales) != 1 or
                grupos_actuales[0] not in ROLES
            ):
                return Response(
                    {'message': 'El usuario no tiene un rol válido.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            es_principal = (
                usuario.pk == configuracion.administrador_principal_id
            )

            if es_principal and request.user.pk != usuario.pk:
                return Response(
                    {'message': 'No puedes modificar la cuenta del administrador principal.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            serializer = EditarEmpleadoSerializer(
                data=request.data,
                context={'usuario': usuario},
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            datos = serializer.validated_data

            rol_actual = grupos_actuales[0]
            rol_nuevo = datos.get('rol', rol_actual)
            activo_nuevo = datos.get('is_active', usuario.is_active)

            if es_principal and (
                rol_nuevo != 'admin' or not activo_nuevo
            ):
                return Response(
                    {'message': 'El administrador principal no puede cambiar de rol ni desactivarse.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if request.user.pk == usuario.pk and (
                rol_nuevo != rol_actual or not activo_nuevo
            ):
                return Response(
                    {'message': 'No puedes cambiar tu propio rol ni desactivar tu cuenta.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if (
                rol_actual == 'admin' and
                usuario.is_active and
                (rol_nuevo != 'admin' or not activo_nuevo)
            ):
                administradores = (
                    User.objects.filter(
                        groups__name='admin',
                        is_active=True
                    ).distinct().count()
                )

                if administradores <= 1:
                    return Response(
                        {'message': 'No puedes dejar el sistema sin administradores activos.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            for campo in [
                'username',
                'first_name',
                'last_name',
                'email',
                'is_active'
            ]:
                if campo in datos:
                    setattr(usuario, campo, datos[campo])

            cambio_password = 'password' in datos

            if cambio_password:
                usuario.set_password(datos['password'])

            usuario.save()

            if 'telefono' in datos:
                perfil, _ = PerfilUsuario.objects.get_or_create(
                    user=usuario
                )
                perfil.telefono = datos['telefono']
                perfil.save()

            cambio_rol = rol_nuevo != rol_actual

            if cambio_rol:
                grupo, _ = Group.objects.get_or_create(
                    name=rol_nuevo
                )
                usuario.groups.set([grupo])

            if (
                cambio_password or
                cambio_rol or
                not usuario.is_active
            ):
                Token.objects.filter(user=usuario).delete()

        return Response({
            'message': 'Empleado actualizado correctamente.',
            'usuario': EmpleadoSerializer(usuario).data
        })

    def delete(self, request, id):
        with transaction.atomic():
            configuracion = (
                ConfiguracionSistema.objects
                .select_for_update()
                .filter(pk=1)
                .first()
            )

            if (
                configuracion is None or
                not configuracion.completada or
                configuracion.administrador_principal_id is None
            ):
                return Response(
                    {'message': 'La configuración de administradores está incompleta.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            usuario = get_object_or_404(
                User.objects.select_for_update(),
                pk=id
            )

            grupos_actuales = list(
                usuario.groups.values_list('name', flat=True)
            )

            if (
                len(grupos_actuales) != 1 or
                grupos_actuales[0] not in ROLES
            ):
                return Response(
                    {'message': 'El usuario no tiene un rol válido.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if usuario.pk == configuracion.administrador_principal_id:
                return Response(
                    {'message': 'El administrador principal no puede eliminarse.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if request.user.pk == usuario.pk:
                return Response(
                    {'message': 'No puedes eliminar tu propia cuenta.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if not usuario.is_active:
                return Response(
                    {'message': 'Esta cuenta ya está desactivada.'},
                    status=status.HTTP_409_CONFLICT
                )

            if grupos_actuales[0] == 'admin':
                administradores = (
                    User.objects.filter(
                        groups__name='admin',
                        is_active=True
                    ).distinct().count()
                )

                if administradores <= 1:
                    return Response(
                        {'message': 'No puedes dejar el sistema sin administradores activos.'},
                        status=status.HTTP_409_CONFLICT
                    )

            usuario.is_active = False
            usuario.save(update_fields=['is_active'])

            Token.objects.filter(user=usuario).delete()

        return Response({
            'message': 'Empleado desactivado correctamente.',
            'usuario': EmpleadoSerializer(usuario).data
        }, status=status.HTTP_200_OK)
