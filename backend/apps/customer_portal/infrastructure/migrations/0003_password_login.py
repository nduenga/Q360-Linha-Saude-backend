"""Login por email + palavra-passe do Portal Cliente.

`password_hash` guarda o hash Django da palavra-passe (nunca texto). O código
enviado por email para definir/repor a palavra-passe usa a mesma tabela de
desafios que o login antigo, distinguido por `purpose` — assim um código de
«definir palavra-passe» nunca serve para o login por OTP, nem vice-versa.
"""
from django.db import migrations

V0003_UP = """
ALTER TABLE q360.customer_account
    ADD COLUMN password_hash   varchar(256),
    ADD COLUMN password_set_at timestamptz;

ALTER TABLE q360.customer_login_challenge
    ADD COLUMN purpose varchar(20) NOT NULL DEFAULT 'LOGIN',
    ADD CONSTRAINT ck_customer_login_challenge_purpose CHECK (purpose IN ('LOGIN', 'SET_PASSWORD'));
"""

V0003_DOWN = """
ALTER TABLE q360.customer_login_challenge
    DROP CONSTRAINT ck_customer_login_challenge_purpose,
    DROP COLUMN purpose;

ALTER TABLE q360.customer_account
    DROP COLUMN password_set_at,
    DROP COLUMN password_hash;
"""


class Migration(migrations.Migration):
    dependencies = [("customer_portal", "0002_requests_messages_notifications")]
    operations = [migrations.RunSQL(sql=V0003_UP, reverse_sql=V0003_DOWN)]
