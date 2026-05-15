from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [
        migrations.CreateModel('UserProfile', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('currency', models.CharField(default='USD', max_length=3)),
            ('starting_balance', models.FloatField(default=0.0)),
            ('initialized', models.BooleanField(default=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to='auth.user')),
        ]),
        migrations.CreateModel('Broker', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('name', models.CharField(max_length=100)),
            ('spread', models.FloatField(default=1.0)),
            ('wins', models.IntegerField(default=0)),
            ('losses', models.IntegerField(default=0)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='brokers', to='auth.user')),
        ]),
        migrations.CreateModel('Investor', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('name', models.CharField(max_length=100)),
            ('wins', models.IntegerField(default=0)),
            ('losses', models.IntegerField(default=0)),
            ('net_pl', models.FloatField(default=0.0)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='investors', to='auth.user')),
        ]),
        migrations.CreateModel('TokenWallet', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('tokens', models.IntegerField(default=10)),
            ('total_earned', models.IntegerField(default=10)),
            ('total_used', models.IntegerField(default=0)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet', to='auth.user')),
        ]),
        migrations.CreateModel('TokenHistory', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('action', models.CharField(max_length=200)),
            ('change', models.IntegerField()),
            ('balance', models.IntegerField()),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='token_history', to='auth.user')),
        ], options={'ordering': ['-created_at']}),
        migrations.CreateModel('Trade', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('symbol', models.CharField(max_length=20)),
            ('shares', models.IntegerField(default=0)),
            ('entry_price_share', models.FloatField(default=0.0)),
            ('exit_price_share',  models.FloatField(default=0.0)),
            ('profit_per_share',  models.FloatField(default=0.0)),
            ('total_profit',      models.FloatField(default=0.0)),
            ('balance_after',     models.FloatField(default=0.0)),
            ('broker',   models.CharField(blank=True, max_length=100)),
            ('investor', models.CharField(blank=True, max_length=100)),
            ('notes',    models.TextField(blank=True)),
            ('locked',   models.BooleanField(default=False)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trades', to='auth.user')),
        ], options={'ordering': ['id']}),
    ]
