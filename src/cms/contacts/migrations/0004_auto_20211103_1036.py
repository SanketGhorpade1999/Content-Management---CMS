# Generated by Django 3.2.5 on 2021-11-03 10:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cmscontacts', '0003_auto_20210910_0855'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contactinfo',
            name='label',
            field=models.CharField(blank=True, default='', max_length=160),
        ),
        migrations.AlterField(
            model_name='contactinfolocalization',
            name='label',
            field=models.CharField(blank=True, default='', max_length=160),
        ),
    ]
