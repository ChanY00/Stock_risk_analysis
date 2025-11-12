# Generated manually to update DecimalField precision
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentiment', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sentimentanalysis',
            name='positive',
            field=models.DecimalField(decimal_places=4, max_digits=5),
        ),
        migrations.AlterField(
            model_name='sentimentanalysis',
            name='negative',
            field=models.DecimalField(decimal_places=4, max_digits=5),
        ),
    ]











