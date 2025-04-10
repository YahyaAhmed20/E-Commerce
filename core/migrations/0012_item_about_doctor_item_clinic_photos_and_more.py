# Generated by Django 5.1.3 on 2025-03-25 18:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_alter_item_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='about_doctor',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='item',
            name='clinic_photos',
            field=models.ImageField(blank=True, null=True, upload_to='clinic_photos/'),
        ),
        migrations.AlterField(
            model_name='item',
            name='image',
            field=models.ImageField(upload_to='items/'),
        ),
    ]
