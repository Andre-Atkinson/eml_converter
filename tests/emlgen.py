"""Synthesise .eml fixtures with the standard-library email package.

Tests build their inputs at runtime rather than committing sample mail: the
repository's .gitignore deliberately blocks *.eml / *.msg (real messages carry
other people's addresses and attachment payloads), and synthesising also lets
each test construct exactly the edge case it targets.
"""
import pathlib
from email.message import EmailMessage


def make_eml(path, from_=None, to=None, cc=None, subject="Test message",
             plain="Body text.", html=None, attachments=(), message_id=None):
    """Write a MIME .eml to `path` and return it as a pathlib.Path.

    to/cc accept a string or a list of addresses. `attachments` is an iterable
    of dicts with keys data (bytes) and filename (str), plus optional maintype
    and subtype (default application/octet-stream). Pass from_=None to omit the
    From: header, mimicking a message Outlook for Mac sent (the blank-sender
    case). Pass plain=None with html=... for an HTML-only body.
    """
    m = EmailMessage()
    if from_:
        m["From"] = from_
    if to:
        m["To"] = to if isinstance(to, str) else ", ".join(to)
    if cc:
        m["Cc"] = cc if isinstance(cc, str) else ", ".join(cc)
    m["Subject"] = subject
    if message_id:
        m["Message-ID"] = message_id

    if plain is not None:
        m.set_content(plain)
    if html is not None:
        if plain is not None:
            m.add_alternative(html, subtype="html")
        else:
            m.set_content(html, subtype="html")

    for att in attachments:
        m.add_attachment(
            att["data"],
            maintype=att.get("maintype", "application"),
            subtype=att.get("subtype", "octet-stream"),
            filename=att["filename"],
        )

    path = pathlib.Path(path)
    path.write_bytes(m.as_bytes())
    return path
