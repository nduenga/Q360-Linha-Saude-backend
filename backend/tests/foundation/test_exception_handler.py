from __future__ import annotations

from apps.foundation.interfaces.exception_handler import q360_exception_handler
from apps.quote.application.office_converter import OfficeConversionError


def test_document_conversion_unavailable_is_a_problem_response_not_a_server_error():
    response = q360_exception_handler(OfficeConversionError("LibreOffice indisponivel"), {})

    assert response.status_code == 503
    assert response.data["code"] == "DOCUMENT-CONVERSION-UNAVAILABLE"
    assert response.data["title"] == "Conversão de documentos indisponível"
