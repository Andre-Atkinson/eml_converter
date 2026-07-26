"""End-to-end conversion tests.

Each test synthesises an .eml, converts it with the real eml2msg binary, and
verifies the resulting .msg with the inspect_msg oracle - a parser independent
of the MsgKit library that wrote the file. Ground-truth property values (e.g.
Message-ID losing its angle brackets, PR_DISPLAY_TO holding a display name, an
emoji becoming a signed \\u escape) were confirmed against real output.
"""
import emlgen
import oracle


def _run(converter, tmp_path, args=(), **eml_kwargs):
    """Synthesise an .eml, convert it, and return (CompletedProcess, msg_path)."""
    eml = emlgen.make_eml(tmp_path / "message.eml", **eml_kwargs)
    result = converter(*args, eml)
    return result, eml.with_suffix(".msg")


def test_output_is_a_valid_msg(converter, tmp_path):
    result, msg = _run(converter, tmp_path, from_="A <a@x.com>", to="b@y.com",
                       plain="hi", html="<p>hi</p>")
    assert result.returncode == 0, result.stderr
    assert msg.exists()
    view = oracle.read_properties(msg)          # raises if not a valid CFBF
    assert oracle.text(view, "PR_MESSAGE_CLASS") == "IPM.Note"


def test_subject_and_bodies_present(converter, tmp_path):
    subject = "Quarterly report"
    _, msg = _run(converter, tmp_path, from_="A <a@x.com>", to="b@y.com",
                  subject=subject, plain="See below.", html="<p>See below.</p>")
    view = oracle.read_properties(msg)
    assert oracle.text(view, "PR_SUBJECT") == subject
    assert "See below." in oracle.text(view, "PR_BODY")
    assert oracle.has(view, "PR_HTML")
    assert oracle.has(view, "PR_RTF_COMPRESSED")


def test_unicode_subject_is_stored_as_unicode(converter, tmp_path):
    subject = "Grüße und Ω — 你好"
    _, msg = _run(converter, tmp_path, from_="A <a@x.com>", to="b@y.com",
                  subject=subject, plain="x")
    view = oracle.read_properties(msg)
    entry = oracle.prop(view, "PR_SUBJECT")
    assert entry["type"] == "001F"              # PT_UNICODE - no mojibake
    assert entry["text"] == subject


def test_html_body_becomes_encapsulated_rtf(converter, tmp_path):
    html = "<p>Hej v&auml;rlden</p>"
    _, msg = _run(converter, tmp_path, from_="A <a@x.com>", to="b@y.com",
                  plain="Hej", html=html)
    rtf = oracle.decompress_rtf(oracle.read_properties(msg))
    assert rtf is not None
    assert b"\\fromhtml1" in rtf                 # encapsulated-HTML form
    assert html.encode() in rtf                  # original HTML carried verbatim


def test_astral_chars_use_signed_rtf_unicode(converter, tmp_path):
    # U+1F600 -> UTF-16 surrogates 0xD83D/0xDE00 -> signed \u -10179 / -8704.
    # The unsigned forms (55357/56832) would garble the emoji in Outlook; this
    # is the exact edge case Rtf.cs guards against.
    _, msg = _run(converter, tmp_path, from_="A <a@x.com>", to="b@y.com",
                  plain="hi", html="<p>😀</p>")
    rtf = oracle.decompress_rtf(oracle.read_properties(msg))
    assert b"\\u-10179?" in rtf
    assert b"\\u-8704?" in rtf
    assert b"\\u55357" not in rtf
    assert b"\\u56832" not in rtf


def test_plain_text_only_gets_no_rtf(converter, tmp_path):
    _, msg = _run(converter, tmp_path, from_="A <a@x.com>", to="b@y.com",
                  plain="just text", html=None)
    view = oracle.read_properties(msg)
    assert not oracle.has(view, "PR_RTF_COMPRESSED")
    assert oracle.has(view, "PR_BODY")


def test_no_rtf_flag_suppresses_rtf(converter, tmp_path):
    _, msg = _run(converter, tmp_path, args=("--no-rtf",),
                  from_="A <a@x.com>", to="b@y.com", plain="x", html="<p>x</p>")
    view = oracle.read_properties(msg)
    assert not oracle.has(view, "PR_RTF_COMPRESSED")
    assert oracle.has(view, "PR_HTML")


def test_missing_from_warns_and_leaves_sender_blank(converter, tmp_path):
    result, msg = _run(converter, tmp_path, from_=None, to="b@y.com", plain="x")
    assert result.returncode == 0
    assert "no From:" in result.stderr
    view = oracle.read_properties(msg)
    assert not (oracle.text(view, "PR_SENDER_EMAIL_ADDRESS") or "")


def test_from_fallback_populates_sender(converter, tmp_path):
    _, msg = _run(converter, tmp_path,
                  args=("--from", "Andre A <andre@example.com>"),
                  from_=None, to="b@y.com", plain="x")
    view = oracle.read_properties(msg)
    assert oracle.text(view, "PR_SENDER_EMAIL_ADDRESS") == "andre@example.com"
    assert oracle.text(view, "PR_SENDER_NAME") == "Andre A"


def test_recipients_to_and_cc(converter, tmp_path):
    _, msg = _run(converter, tmp_path, from_="A <a@x.com>",
                  to="Bob <bob@y.com>", cc="Carol <carol@z.com>", plain="x")
    view = oracle.read_properties(msg)
    assert len(view["recipients"]) == 2
    addresses = oracle.all_text(view, "PR_EMAIL_ADDRESS")
    assert "bob@y.com" in addresses
    assert "carol@z.com" in addresses
    assert oracle.text(view, "PR_DISPLAY_TO") == "Bob"
    assert oracle.text(view, "PR_DISPLAY_CC") == "Carol"


def test_attachment_bytes_and_long_name_survive(converter, tmp_path):
    data = bytes(range(256)) * 4                 # 1 KiB, every byte value
    name = "réport – final (v2).bin"            # unicode, spaces, en-dash
    _, msg = _run(converter, tmp_path, from_="A <a@x.com>", to="b@y.com",
                  plain="see attached",
                  attachments=[{"data": data, "filename": name}])
    view = oracle.read_properties(msg)
    assert len(view["attachments"]) == 1
    assert oracle.text(view, "PR_ATTACH_LONG_FILENAME") == name
    assert oracle.raw(view, "PR_ATTACH_DATA_BIN") == data


def test_message_id_and_transport_headers(converter, tmp_path):
    _, msg = _run(converter, tmp_path, from_="A <a@x.com>", to="b@y.com",
                  plain="x", message_id="<abc123@example.com>")
    view = oracle.read_properties(msg)
    assert oracle.text(view, "PR_INTERNET_MESSAGE_ID") == "abc123@example.com"
    assert oracle.has(view, "PR_TRANSPORT_MESSAGE_HEADERS")
