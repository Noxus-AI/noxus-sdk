"""Email parsing for plugin authors.

A small, self-contained helper for turning a raw RFC-822 message into a typed
:class:`Email` whose attachments (and inline images) are persisted to platform
storage as :class:`~noxus_sdk.files.File` objects. Use it from a node's
``call()`` when a node receives raw email bytes and needs the subject/body plus
downloadable attachments::

    import email
    from noxus_sdk.email import Email

    msg = email.message_from_bytes(raw, policy=email.policy.default)
    parsed = await Email.from_email_object(ctx, msg)
    text = parsed.to_text()
    for att in parsed.attachments:
        data = await att.get_content(ctx)

Attachment persistence goes through the same host file callbacks as
:meth:`File.from_bytes`, so nothing here needs network access back to the
platform.
"""

from __future__ import annotations

import asyncio
import mimetypes
import tempfile
import zipfile
from email.message import EmailMessage, Message
from typing import TYPE_CHECKING, Iterator

from loguru import logger
from markdownify import markdownify
from pydantic import BaseModel

from noxus_sdk.files import File

if TYPE_CHECKING:
    from noxus_sdk.plugins.context import RemoteExecutionContext


def iter_email_attachment_parts(
    email_msg: EmailMessage, body_part: Message | None
) -> Iterator[EmailMessage]:
    """Yield every leaf part that is real content to persist — attachments *and*
    inline images — regardless of how the sender nested the MIME tree.

    ``EmailMessage.iter_attachments()`` can't be used here: it treats a whole
    ``multipart/related`` subtree as "the body" and never descends into it, so an
    inline image silently disappears the moment a sibling attachment promotes a
    ``multipart/mixed`` wrapper around the related part. Walking every leaf and
    excluding only the textual body parts is structure-independent.
    """
    for part in email_msg.walk():
        if not isinstance(part, EmailMessage) or part.is_multipart():
            continue
        if part is body_part:
            continue
        # The body and its plain/html alternative carry no disposition and no
        # filename — everything else (inline images, real attachments) is content.
        if (
            part.get_content_disposition() is None
            and not part.get_filename()
            and part.get_content_type() in ("text/plain", "text/html")
        ):
            continue
        yield part


def email_attachment_filename(part: Message, index: int) -> str:
    """A usable filename for an attachment part, deriving one from the content
    type when the part carries no filename (common for inline images)."""
    name = part.get_filename()
    if name:
        return name
    ext = mimetypes.guess_extension(part.get_content_type()) or ""
    return f"file{index}{ext}"


class Email(BaseModel):
    """A parsed email: headers, a markdown-ish body, and persisted attachments.

    Build one with :meth:`from_email_object`. ``attachments`` (and ``eml``) are
    :class:`~noxus_sdk.files.File` references already saved to platform storage.
    """

    sender: str
    receiver: list[str]
    cc: list[str]
    subject: str
    attachments: list[File]
    date: str
    body: str
    eml: File | None = None

    @classmethod
    async def from_email_object(
        cls,
        ctx: RemoteExecutionContext,
        _email: EmailMessage,
        load_attachments: bool = True,
        zip_attachments: bool = False,
    ) -> Email:
        """Parse a Python :class:`email.message.EmailMessage` into an :class:`Email`.

        The HTML (or plain) body is converted to markdown. When
        ``load_attachments`` is true, attachment and inline-image parts are
        persisted to platform storage; ``zip_attachments`` collapses them into a
        single ``attachments.zip`` file instead of one file per part.
        """
        receiver = _email["To"] or ""
        sender = _email["From"] or ""
        subject = _email["Subject"] or ""
        date = _email["Date"] or ""
        cc = _email.get("CC", "") or ""
        _body = _email.get_body(preferencelist=("html", "plain"))
        if _body is not None:
            try:
                body = _body.get_content()
                if "html" in _body.get_content_type():
                    body = await asyncio.get_running_loop().run_in_executor(
                        None, markdownify, body
                    )
            except Exception as e:
                logger.opt(exception=e).warning(
                    "Failed parsing body properly, attaching raw body."
                )
                try:
                    body = _body.as_string()
                except Exception as e:
                    logger.opt(exception=e).warning("Failed parsing body as string")
                    body = "<ERROR - Failed parsing body>"
        else:
            body = "<No body>"

        attachments: list[File] = []
        if load_attachments:
            coroutine_attachments = []
            _attachments = list(iter_email_attachment_parts(_email, _body))
            if len(_attachments) > 0:
                if zip_attachments:
                    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
                        with zipfile.ZipFile(tmp.name, "w") as z:
                            for i, part in enumerate(_attachments):
                                if not part:
                                    continue
                                _part = part.get_content()
                                if not isinstance(_part, bytes):
                                    _part = str(_part).encode()
                                z.writestr(email_attachment_filename(part, i), _part)
                        tmp.seek(0)
                        coroutine_attachments.append(
                            File.from_bytes_internal_uri(
                                ctx,
                                data=tmp.read(),
                                name="attachments.zip",
                                content_type="application/zip",
                            )
                        )
                else:
                    for i, part in enumerate(_attachments):
                        if not part:
                            continue
                        _part = part.get_content()
                        if not isinstance(_part, bytes):
                            _part = str(_part).encode()
                        coroutine_attachments.append(
                            File.from_bytes_internal_uri(
                                ctx,
                                _part,
                                name=email_attachment_filename(part, i),
                                content_type=part.get_content_type(),
                            )
                        )
            attachments = list(await asyncio.gather(*coroutine_attachments))
        return cls(
            sender=sender,
            receiver=[receiver],
            cc=[cc],
            subject=subject,
            date=date,
            body=body,
            attachments=attachments,
        )

    def to_text(self) -> str:
        """A plain-text rendering of the email, handy as LLM/tool input."""
        return f"""
From: {self.sender}
To: {self.receiver}
CC: {self.cc}
Sent Date: {self.date}
Subject: {self.subject}
Email body:

{self.body}"""
