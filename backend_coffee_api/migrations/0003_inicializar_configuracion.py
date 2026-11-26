
from django.db import migrations


def inicializar_configuracion(apps, schema_editor):
    ConfiguracionSistema = apps.get_model('backend_coffee_api', 'ConfiguracionSistema')
    ConfiguracionSistema.objects.using(schema_editor.connection.alias).get_or_create(id=1, defaults={'completada': False})


class Migration(migrations.Migration):
    dependencies = [
        ('backend_coffee_api', '0002_configuracionsistema'),
    ]

    operations = [
        migrations.RunPython(inicializar_configuracion, migrations.RunPython.noop),
    ]
