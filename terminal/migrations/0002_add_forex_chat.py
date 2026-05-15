from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('terminal', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # ── Add fields to Trade ───────────────────────────────
        migrations.AddField('Trade', 'trade_type',
            models.CharField(max_length=10, default='STOCK',
                choices=[('STOCK','Stock'),('FOREX','Forex')])),
        migrations.AddField('Trade', 'pair',
            models.CharField(max_length=10, blank=True, default='')),
        migrations.AddField('Trade', 'direction',
            models.CharField(max_length=4, blank=True, default='')),
        migrations.AddField('Trade', 'lot_size',
            models.FloatField(default=0.0)),
        migrations.AddField('Trade', 'entry_price',
            models.FloatField(default=0.0)),
        migrations.AddField('Trade', 'exit_price',
            models.FloatField(default=0.0)),
        migrations.AddField('Trade', 'pips',
            models.FloatField(default=0.0)),
        migrations.AddField('Trade', 'screenshot_b64',
            models.TextField(blank=True, default='')),
        migrations.AddField('Trade', 'rating',
            models.IntegerField(default=0)),

        # ── ChatMessage model ─────────────────────────────────
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('message', models.CharField(max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chat_messages',
                    to='auth.user')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(fields=['created_at'], name='chat_created_idx'),
        ),
    ]
