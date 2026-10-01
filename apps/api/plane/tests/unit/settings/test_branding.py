# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch

import pytest
from django.template.loader import render_to_string

from plane.bgtasks.magic_link_code_task import magic_link
from plane.settings.openapi import SPECTACULAR_SETTINGS
from plane.utils.email import generate_plain_text_from_html


@pytest.mark.unit
@pytest.mark.parametrize(
    "template",
    [
        "emails/auth/magic_signin.html",
        "emails/auth/forgot_password.html",
        "emails/invitations/workspace_invitation.html",
        "emails/invitations/project_invitation.html",
        "emails/notifications/project_addition.html",
        "emails/notifications/webhook-deactivate.html",
        "emails/user/user_activation.html",
        "emails/user/user_deactivation.html",
        "emails/user/email_updated.html",
        "emails/exports/analytics.html",
        "emails/test_email.html",
    ],
)
def test_email_identity_and_dynamic_content(template):
    html = render_to_string(
        template,
        {
            "code": "123456",
            "first_name": "Ada",
            "inviter_first_name": "Ada",
            "workspace_name": "Example workspace",
            "project_name": "Example project",
            "email": "ada@example.com",
        },
    )
    text = generate_plain_text_from_html(html)
    assert "Birdplane" in text
    assert "media.docs.plane.so/logo/" not in html
    if template.endswith("magic_signin.html"):
        assert "123456" in text
    if template.endswith("workspace_invitation.html"):
        assert "Example workspace" in text


@pytest.mark.unit
def test_login_email_subject_and_body_use_fork_name():
    module = "plane.bgtasks.magic_link_code_task"
    with (
        patch(
            f"{module}.get_email_configuration",
            return_value=("smtp", "", "", "25", "0", "0", "sender@example.com"),
        ),
        patch(f"{module}.get_connection"),
        patch(f"{module}.EmailMultiAlternatives") as mail,
    ):
        magic_link.run("ada@example.com", "key", "123456")

    mail.assert_called_once()
    assert mail.call_args.kwargs["subject"] == "Your unique Birdplane login code is 123456"
    assert "Birdplane" in mail.call_args.kwargs["body"]
    assert mail.call_args.kwargs["to"] == ["ada@example.com"]
    mail.return_value.send.assert_called_once()


@pytest.mark.unit
def test_api_docs_identify_fork_and_preserve_api_namespace():
    assert SPECTACULAR_SETTINGS["TITLE"] == "The Birdplane REST API"
    assert SPECTACULAR_SETTINGS["CONTACT"]["url"] == "https://github.com/dasomji/birdplane"
    assert SPECTACULAR_SETTINGS["SCHEMA_PATH_PREFIX"] == "/api/v1/"
