# Generated by Django 5.1.3 on 2025-03-25 18:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_remove_coupon_active_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='item',
            name='category',
            field=models.CharField(choices=[('L', 'Laser treatments'), ('LP', 'Liposuction'), ('BX', 'Botox injections')], max_length=2),
        ),
    ]
