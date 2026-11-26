
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from backend_coffee_api.authentication import BearerTokenAuthentication
from backend_coffee_api.serializers import LoginSerializer, UserSerializer
from backend_coffee_api.models import ConfiguracionSistema


class CustomAuthToken(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        configuracion = ConfiguracionSistema.objects.filter(pk=1, completada=True).exists()

        if not configuracion:
            return Response({'message': 'Primero debes completar la instalación de Backend Coffee.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=usuario)

        return Response({
            'message': 'Inicio de sesión correcto.',
            'token': token.key,
            'usuario': UserSerializer(usuario).data
        }, status=status.HTTP_200_OK)


class UsuarioActual(APIView):
    authentication_classes = [BearerTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        usuario = request.user
        grupos = list(usuario.groups.values_list('name', flat=True))

        if len(grupos) != 1 or grupos[0] not in ['admin', 'colaborador', 'cocinero']:
            return Response({'message': 'El usuario no tiene un rol válido.'}, status=status.HTTP_403_FORBIDDEN)

        return Response({
            'usuario': UserSerializer(usuario).data
        }, status=status.HTTP_200_OK)


class Logout(APIView):
    authentication_classes = [BearerTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()

        return Response({
            'message': 'Sesión cerrada correctamente.'
        }, status=status.HTTP_200_OK)
