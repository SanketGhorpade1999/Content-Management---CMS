# Generated by Django 3.2.5 on 2021-12-29 09:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cmsmenus', '0010_alter_navigationbaritemlocalization_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='navigationbaritem',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='navigationbaritemlocalization',
            name='name',
            field=models.CharField(max_length=100),
        ),
    ]
