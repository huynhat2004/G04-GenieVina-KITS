from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import CustomerCreate, CustomerPatch, SignupMethod


@pytest.fixture
def payload():
    return {
        'customerCode': 'DEMO-001', 'name': 'Khách giả lập', 'country': 'VN',
        'signupMethod': 'EMAIL', 'signedUpAt': '2026-11-24T09:00:00+07:00',
    }


def test_create_trims_text_and_preserves_the_timestamp_instant(payload):
    model = CustomerCreate.model_validate({**payload, 'customerCode': ' DEMO-001 ',
                                          'name': '  Khách giả lập  ', 'country': ' VN '})
    assert model.customerCode == 'DEMO-001'
    assert model.name == 'Khách giả lập'
    assert model.country == 'VN'
    assert model.signedUpAt.astimezone(timezone.utc) == datetime(2026, 11, 24, 2, tzinfo=timezone.utc)


@pytest.mark.parametrize('method', list(SignupMethod))
def test_create_accepts_each_supported_signup_method(payload, method):
    assert CustomerCreate.model_validate({**payload, 'signupMethod': method.value}).signupMethod == method


@pytest.mark.parametrize('field,limit', [('customerCode', 40), ('name', 200)])
def test_text_limits_are_applied_after_trimming(payload, field, limit):
    model = CustomerCreate.model_validate({**payload, field: ' ' + 'X' * limit + ' '})
    assert getattr(model, field) == 'X' * limit
    with pytest.raises(ValidationError):
        CustomerCreate.model_validate({**payload, field: 'X' * (limit + 1)})


@pytest.mark.parametrize('value', ['', ' ', '\t\n'])
@pytest.mark.parametrize('field', ['customerCode', 'name'])
def test_required_text_cannot_be_blank(payload, field, value):
    with pytest.raises(ValidationError):
        CustomerCreate.model_validate({**payload, field: value})


@pytest.mark.parametrize('field', ['customerCode', 'name', 'country', 'signupMethod', 'signedUpAt'])
def test_create_requires_every_field(payload, field):
    del payload[field]
    with pytest.raises(ValidationError):
        CustomerCreate.model_validate(payload)


@pytest.mark.parametrize('value', ['2026-11-24T09:00:00', 'invalid', None])
def test_create_rejects_missing_timezone_and_invalid_dates(payload, value):
    with pytest.raises(ValidationError):
        CustomerCreate.model_validate({**payload, 'signedUpAt': value})


@pytest.mark.parametrize('model', [CustomerCreate, CustomerPatch])
def test_clients_cannot_mass_assign_internal_fields(payload, model):
    with pytest.raises(ValidationError):
        model.model_validate({**payload, 'id': 123, 'role': 'ADMIN'})


def test_patch_only_includes_supplied_fields():
    model = CustomerPatch.model_validate({'name': ' Tên mới '})
    assert model.model_dump(exclude_unset=True) == {'name': 'Tên mới'}


@pytest.mark.parametrize('field', ['customerCode', 'name', 'country', 'signupMethod', 'signedUpAt'])
def test_patch_rejects_explicit_null_even_with_another_valid_change(field):
    with pytest.raises(ValidationError):
        CustomerPatch.model_validate({'name': 'Tên mới', field: None})


def test_patch_rejects_empty_body():
    with pytest.raises(ValidationError):
        CustomerPatch.model_validate({})


def test_patch_can_update_all_customer_fields_together(payload):
    assert CustomerPatch.model_validate(payload).model_fields_set == set(payload)
