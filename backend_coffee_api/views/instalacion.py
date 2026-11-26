
import secrets
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
from backend_coffee_api.models import PerfilUsuario, ConfiguracionSistema
from backend_coffee_api.serializers import UserSerializer, InstalacionAdminSerializer


class EstadoInstalacionView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        configuracion = ConfiguracionSistema.objects.filter(pk=1).first()

        if configuracion is None:
            return Response({'message': 'La configuración inicial no existe. Revisa las migraciones.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            'configurado': configuracion.completada,
            'requiere_configuracion': not configuracion.completada
        })


class RegistrarAdminInicialView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        clave_esperada = settings.BACKEND_COFFEE_SETUP_KEY
        clave_recibida = request.headers.get('X-Setup-Key', '')

        if not clave_esperada:
            return Response({'message': 'No se configuró la clave de instalación.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if not secrets.compare_digest(clave_recibida, clave_esperada):
            return Response({'message': 'Clave de instalación incorrecta.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            configuracion = ConfiguracionSistema.objects.select_for_update().filter(pk=1).first()

            if configuracion is None:
                return Response({'message': 'No existe la configuración inicial en MySQL.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            if configuracion.completada:
                return Response({'message': 'Backend Coffee ya fue configurado.'}, status=status.HTTP_403_FORBIDDEN)

            if User.objects.filter(groups__name='admin').exists():
                return Response({'message': 'Ya existe un administrador. Revisa la configuración.'}, status=status.HTTP_409_CONFLICT)

            serializer = InstalacionAdminSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            datos = serializer.validated_data

            usuario = User.objects.create_user(
                username=datos['username'],
                first_name=datos['first_name'],
                last_name=datos['last_name'],
                email=datos['email'],
                password=datos['password'],
                is_staff=False,
                is_superuser=False
            )

            grupo, created = Group.objects.get_or_create(name='admin')
            usuario.groups.add(grupo)

            PerfilUsuario.objects.create(user=usuario, telefono=datos.get('telefono', ''))
            token = Token.objects.create(user=usuario)


            configuracion.administrador_principal = usuario
            configuracion.completada = True
            configuracion.fecha_configuracion = timezone.now()
            configuracion.save(update_fields=[
                'administrador_principal',
                'completada',
                'fecha_configuracion'
            ])

            return Response({
                'message': 'Administrador inicial registrado correctamente.',
                'token': token.key,
                'usuario': UserSerializer(usuario).data
            }, status=status.HTTP_201_CREATED)
