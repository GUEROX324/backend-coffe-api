"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from backend_coffee_api.views import instalacion
from backend_coffee_api.views import auth
from backend_coffee_api.views import usuarios
from backend_coffee_api.views import categorias
from backend_coffee_api.views import productos
from backend_coffee_api.views import menu
from backend_coffee_api.views import caja
from backend_coffee_api.views import pedidos
from backend_coffee_api.views import cocina
from backend_coffee_api.views import entregas
from backend_coffee_api.views import stats
from backend_coffee_api.views import personalizacion

urlpatterns = [
    # Configuración inicial
    path('api/instalacion/estado/', instalacion.EstadoInstalacionView.as_view()),
    path('api/instalacion/admin/', instalacion.RegistrarAdminInicialView.as_view()),

    # Autenticación
    path('api/token/', auth.CustomAuthToken.as_view()),
    path('api/usuario/', auth.UsuarioActual.as_view()),
    path('api/logout/', auth.Logout.as_view()),

    # Administración del personal
    path('api/usuarios/', usuarios.UsuariosView.as_view()),
    path('api/usuarios/<int:id>/', usuarios.UsuarioDetalleView.as_view()),

    # Categorías
    path('api/categorias/', categorias.CategoriasView.as_view()),
    path('api/categorias/<int:id>/', categorias.CategoriaDetalleView.as_view()),

    # Productos
    path('api/productos/', productos.ProductosView.as_view()),
    path('api/productos/<int:id>/', productos.ProductoDetalleView.as_view()),

    # Menú público
    path('api/menu/', menu.MenuPublicoView.as_view()),


    # Caja
    path('api/caja/abrir/', caja.AbrirCajaView.as_view()),
    path('api/caja/turno/', caja.TurnoActivoView.as_view()),
    path('api/caja/resumen/', caja.CajaResumenView.as_view()),
    path('api/caja/movimientos/', caja.MovimientosCajaView.as_view()),
    path('api/caja/cerrar/', caja.CerrarCajaView.as_view()),
    path('api/caja/historial/', caja.HistorialCajaView.as_view()),


    # Pedidos
    path('api/pedidos/', pedidos.PedidosView.as_view()),
    path('api/pedidos/<int:id>/', pedidos.PedidoDetalleView.as_view()),

    # Cocina
    path('api/cocina/pedidos/', cocina.PedidosCocinaView.as_view()),
    path('api/cocina/pedidos/<int:id>/', cocina.PedidoCocinaDetalleView.as_view()),
    path('api/cocina/preparaciones/<int:id>/', cocina.ActualizarPreparacionView.as_view()),
    
    # Entregas
    path('api/entregas/pendientes/', entregas.PedidosListosView.as_view()),
    path('api/entregas/', entregas.EntregasView.as_view()),
    path('api/entregas/<int:id>/', entregas.EntregaDetalleView.as_view()),


    # Reportes y estadísticas
    path('api/stats/resumen/', stats.StatsResumenView.as_view()),
    path('api/stats/ventas/', stats.StatsVentasView.as_view()),
    path('api/stats/productos/', stats.StatsProductosView.as_view()),
    path('api/stats/pedidos/', stats.StatsPedidosView.as_view()),
    path('api/stats/caja/', stats.StatsCajaView.as_view()),
    path('api/caja/historial/<int:turno_id>/',caja.DetalleHistorialCajaView.as_view(),name='detalle-historial-caja'),

    # VARIANTES
    path('api/variantes/', personalizacion.VariantesView.as_view()),
    path('api/variantes/<int:id>/', personalizacion.VarianteDetalleView.as_view()),

    # INGREDIENTES
    path('api/ingredientes/', personalizacion.IngredientesView.as_view()),
    path('api/ingredientes/<int:id>/', personalizacion.IngredienteDetalleView.as_view()),

    # RECETAS
    path('api/recetas/', personalizacion.RecetasView.as_view()),
    path('api/recetas/<int:id>/', personalizacion.RecetaDetalleView.as_view()),

    # EXTRAS
    path('api/extras/<int:id>/', personalizacion.ExtraDetalleView.as_view()),
    path('api/extras/', personalizacion.ExtrasView.as_view()),

    # EXTRAS PERMITIDOS
    path('api/extras-permitidos/', personalizacion.ExtrasPermitidosView.as_view()),
    path('api/extras-permitidos/<int:id>/', personalizacion.ExtraPermitidoDetalleView.as_view()),


]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
