# Generated manually for Watchlist user field addition

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('analysis', '0004_stocksimilarity'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='watchlist',
            options={'ordering': ['-updated_at']},
        ),
        migrations.AddField(
            model_name='watchlist',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='watchlists', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='watchlist',
            unique_together={('user', 'name')},
        ),
    ]

