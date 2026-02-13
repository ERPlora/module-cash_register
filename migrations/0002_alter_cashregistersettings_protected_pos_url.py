from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cash_register', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cashregistersettings',
            name='protected_pos_url',
            field=models.CharField(
                blank=True,
                default='/m/sales/pos/',
                help_text='URL that requires an open cash session.',
                max_length=200,
                verbose_name='Protected POS URL',
            ),
        ),
        # Update existing rows that still have the old default
        migrations.RunSQL(
            sql="UPDATE cash_register_settings SET protected_pos_url = '/m/sales/pos/' WHERE protected_pos_url = '/modules/sales/pos/';",
            reverse_sql="UPDATE cash_register_settings SET protected_pos_url = '/modules/sales/pos/' WHERE protected_pos_url = '/m/sales/pos/';",
        ),
    ]
