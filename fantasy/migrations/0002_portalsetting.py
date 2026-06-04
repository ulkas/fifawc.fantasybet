from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fantasy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=80, unique=True)),
                ("value", models.TextField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["key"]},
        ),
    ]
