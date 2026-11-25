import base64
import hashlib

import pytest

from app.sessions import verify_password
from app.operations import OrderCreate, StatusUpdate
from pydantic import ValidationError


def test_password_hash_compatibility_and_rejection():
    digest = base64.b64encode(hashlib.pbkdf2_hmac('sha256',b'test-password',b'salt',600000)).decode()
    encoded = 'pbkdf2_sha256$600000$salt$'+digest
    assert verify_password('test-password',encoded)
    assert not verify_password('wrong',encoded)
    for invalid in ['plain-text','other$600000$salt$'+digest,'pbkdf2_sha256$9999999999$salt$'+digest]:
        assert not verify_password('test-password',invalid)


@pytest.mark.parametrize('amount', [0,-1,'NaN','Infinity','1.001','10000000000000000'])
def test_order_amount_validation(amount):
    with pytest.raises(ValidationError):
        OrderCreate(customerId=1,packageName='Basic',amount=amount)


@pytest.mark.parametrize('reason', ['', '   ', None])
def test_status_change_requires_nonblank_reason(reason):
    with pytest.raises(ValidationError):
        StatusUpdate(newStatus='PAID',reason=reason)
