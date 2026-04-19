from adv_archon.core.privacy import PIIRedactor


def test_pii_redactor_redacts_and_restores_supported_values() -> None:
    redactor = PIIRedactor()
    source = (
        "Escribe a pablo@example.com, llama al +34 612 34 56 78, "
        "usa ES9121000418450200051332 y DNI 12345678Z."
    )

    result = redactor.redact_text(source)

    assert "__PII_EMAIL_1__" in result.text
    assert "__PII_PHONE_1__" in result.text
    assert "__PII_IBAN_1__" in result.text
    assert "__PII_SPANISH_ID_1__" in result.text

    restored = redactor.restore_text(result.text, result.replacements)

    assert restored == source

