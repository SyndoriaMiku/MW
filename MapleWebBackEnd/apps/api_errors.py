"""
One error shape for every API response with status >= 400.

Views return errors in several legacy shapes ({"detail"}, {"error"},
{"success": false, "message"}, serializer field dicts, plain lists). The
renderer below adds, without removing any legacy key:

    code     machine-readable string (an explicit "code" key wins)
    message  human-readable summary
    fields   {field: [messages]} for validation errors, else {}
"""
from rest_framework.renderers import JSONRenderer

LEGACY_MESSAGE_KEYS = ('detail', 'error', 'message')

STATUS_CODES = {
    400: 'bad_request',
    401: 'not_authenticated',
    403: 'permission_denied',
    404: 'not_found',
    405: 'method_not_allowed',
    406: 'not_acceptable',
    409: 'conflict',
    415: 'unsupported_media_type',
    429: 'throttled',
}
GENERIC_DETAIL_CODES = {'invalid', 'error'}


def _default_code(status_code):
    return 'server_error' if status_code >= 500 else STATUS_CODES.get(status_code, 'error')


def _messages(value):
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def build_error_envelope(data, status_code):
    """Return `data` with code/message/fields added for an error response."""
    if isinstance(data, (list, tuple)):
        messages = [str(item) for item in data]
        return {
            'code': 'validation_error',
            'message': messages[0] if messages else 'Invalid input.',
            'fields': {},
            'non_field_errors': messages,
        }
    if not isinstance(data, dict):
        return {'code': _default_code(status_code), 'message': str(data), 'fields': {}}

    body = dict(data)
    legacy_key = next((key for key in LEGACY_MESSAGE_KEYS if key in body), None)

    fields = {}
    if legacy_key is None:
        # A bare dict with no message key is DRF's field-error shape.
        fields = {
            key: value if isinstance(value, dict) else _messages(value)
            for key, value in body.items()
            if key != 'code'
        }

    if isinstance(body.get('code'), str):
        code = body['code']
    elif legacy_key and getattr(body[legacy_key], 'code', None) not in (None, *GENERIC_DETAIL_CODES):
        code = body[legacy_key].code
    elif fields:
        code = 'validation_error'
    else:
        code = _default_code(status_code)

    if legacy_key is not None:
        message = str(body[legacy_key])
    elif fields:
        first = next(iter(fields.values()))
        message = first[0] if isinstance(first, list) and first else str(first)
    else:
        message = 'Request failed.'

    body['code'] = code
    body.setdefault('message', message)
    body['fields'] = fields
    return body


class ErrorEnvelopeJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get('response')
        if response is not None and response.status_code >= 400 and data is not None:
            data = build_error_envelope(data, response.status_code)
        return super().render(data, accepted_media_type, renderer_context)
