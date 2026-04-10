from django.db import migrations, models


class Migration(migrations.Migration):
    """
    column is_barcode_locked มีอยู่แล้วใน DB (จาก migration 0041 ที่เคย deploy)
    migration นี้แค่ sync Django model state + set DB DEFAULT ไม่ให้ NOT NULL error
    """

    dependencies = [
        ('stocks', '0040_add_barcode_to_salesdeliverylog'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='salesdeliverylog',
                    name='is_barcode_locked',
                    field=models.BooleanField(default=False, verbose_name='ล็อค'),
                ),
            ],
            database_operations=[
                # column อาจมีอยู่แล้ว (จาก 0041) → ใส่ DEFAULT ป้องกัน NOT NULL
                migrations.RunSQL(
                    sql="""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_name='stocks_salesdeliverylog'
                                AND column_name='is_barcode_locked'
                            ) THEN
                                ALTER TABLE stocks_salesdeliverylog
                                ADD COLUMN is_barcode_locked boolean NOT NULL DEFAULT false;
                            ELSE
                                ALTER TABLE stocks_salesdeliverylog
                                ALTER COLUMN is_barcode_locked SET DEFAULT false;
                            END IF;
                        END $$;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
