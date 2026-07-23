using System.Text;

namespace Eml2Msg;

/// <summary>
/// Wraps an HTML body as encapsulated RTF (\fromhtml1) - the form Outlook itself
/// uses to carry HTML mail in PR_RTF_COMPRESSED. The original HTML is preserved
/// verbatim inside \*\htmltag destinations, so nothing is re-rendered or lost:
/// a reader that understands RTF recovers the exact HTML back out.
/// Format per [MS-OXRTFEX].
/// </summary>
internal static class RtfEncapsulator
{
    public static string FromHtml(string html)
    {
        var rtf = new StringBuilder(html.Length + 512);

        rtf.Append(@"{\rtf1\ansi\ansicpg1252\fromhtml1\deff0");
        rtf.Append(@"{\fonttbl{\f0\fswiss\fcharset0 Arial;}}");
        rtf.Append('\n');
        rtf.Append(@"{\*\htmltag64}");
        rtf.Append('\n');
        rtf.Append(@"{\*\htmltag ");

        for (var i = 0; i < html.Length; i++)
        {
            var c = html[i];

            switch (c)
            {
                case '\t':
                    rtf.Append(@"\tab ");
                    continue;

                case '\r':
                    // Consume the LF of a CRLF pair so Windows-newline HTML
                    // doesn't come out double-spaced.
                    if (i + 1 < html.Length && html[i + 1] == '\n') i++;
                    rtf.Append("\\par\n");
                    continue;

                case '\n':
                    rtf.Append("\\par\n");
                    continue;

                case '{' or '}' or '\\':
                    rtf.Append('\\').Append(c);
                    continue;
            }

            // Remaining control characters have no RTF representation.
            if (c < 32) continue;

            if (c <= 127)
            {
                rtf.Append(c);
            }
            else if (c <= 255)
            {
                rtf.Append("\\'").Append(((int)c).ToString("x2"));
            }
            else
            {
                // \uN takes a *signed* 16-bit value, so anything above 0x7FFF -
                // which includes every surrogate, i.e. all astral characters -
                // has to be written as its negative equivalent.
                var code = (int)c;
                if (code > 32767) code -= 65536;
                rtf.Append("\\u").Append(code).Append('?');
            }
        }

        rtf.Append(" }}");
        rtf.Append('\n');
        return rtf.ToString();
    }
}
