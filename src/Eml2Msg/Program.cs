using System.Text;
using MimeKit;

namespace Eml2Msg;

/// <summary>
/// Converts Outlook-for-Mac .eml files into Windows Outlook .msg files.
/// Usage: eml2msg [--outdir DIR] [--overwrite] &lt;file-or-folder&gt; [more...]
/// </summary>
internal static class Program
{
    private static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.UTF8;

        if (args.Length == 0 || args.Contains("-h") || args.Contains("--help"))
        {
            PrintUsage();
            return args.Length == 0 ? 2 : 0;
        }

        string? outDir = null;
        var overwrite = false;
        var rtf = true;
        var inputs = new List<string>();

        // Outlook for Mac omits From: on messages you sent yourself, which lands in
        // Windows Outlook as a blank sender. Fall back to this identity when that happens.
        var fallbackFrom = Environment.GetEnvironmentVariable("EML2MSG_FROM");

        for (var i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--outdir" or "-o":
                    if (++i >= args.Length)
                    {
                        Console.Error.WriteLine("error: --outdir requires a directory");
                        return 2;
                    }
                    outDir = args[i];
                    break;
                case "--from" or "-f":
                    if (++i >= args.Length)
                    {
                        Console.Error.WriteLine("error: --from requires an address");
                        return 2;
                    }
                    fallbackFrom = args[i];
                    break;
                case "--no-rtf":
                    rtf = false;
                    break;
                case "--overwrite":
                    overwrite = true;
                    break;
                default:
                    inputs.Add(args[i]);
                    break;
            }
        }

        var emlFiles = ResolveInputs(inputs, out var badPaths);
        foreach (var bad in badPaths)
            Console.Error.WriteLine($"skipped: no such file or folder - {bad}");

        if (emlFiles.Count == 0)
        {
            Console.Error.WriteLine("error: no .eml files found in the given paths");
            return 1;
        }

        if (outDir is not null)
            Directory.CreateDirectory(outDir);

        var converted = 0;
        var failed = 0;

        foreach (var eml in emlFiles)
        {
            var targetDir = outDir ?? Path.GetDirectoryName(eml) ?? ".";
            var msg = Path.Combine(targetDir, Path.GetFileNameWithoutExtension(eml) + ".msg");

            if (!overwrite)
                msg = MakeUnique(msg);

            try
            {
                Convert(eml, msg, fallbackFrom, rtf);
                Console.WriteLine($"ok: {Path.GetFileName(eml)} -> {Path.GetFileName(msg)}");
                converted++;
            }
            catch (Exception ex)
            {
                // Leave no zero-byte husk behind if the writer failed midway.
                TryDelete(msg);
                Console.Error.WriteLine($"FAILED: {Path.GetFileName(eml)} - {ex.Message}");
                failed++;
            }
        }

        Console.WriteLine($"\n{converted} converted, {failed} failed.");
        return failed > 0 ? 1 : 0;
    }

    /// <summary>
    /// Converts one .eml, repairing a missing From: header first. Outlook for Mac
    /// leaves From: off messages you sent, which becomes an empty PR_SENDER_NAME
    /// and shows as a blank sender in Windows Outlook.
    /// </summary>
    private static void Convert(string emlPath, string msgPath, string? fallbackFrom, bool rtf)
    {
        var message = MimeMessage.Load(emlPath);

        if (rtf)
            AddRtfBody(message);

        if (message.From.Count == 0)
        {
            if (string.IsNullOrWhiteSpace(fallbackFrom))
            {
                Console.Error.WriteLine(
                    $"  warning: {Path.GetFileName(emlPath)} has no From: header - " +
                    "the sender will be blank in Outlook. Use --from to set one.");
            }
            else
            {
                message.From.Add(MailboxAddress.Parse(fallbackFrom));
            }
        }

        using var eml = new MemoryStream();
        message.WriteTo(eml);
        eml.Position = 0;

        using var msg = File.Create(msgPath);
        MsgKit.Converter.ConvertEmlToMsg(eml, msg);
    }

    /// <summary>
    /// Gives the message an RTF body derived from its HTML, so the .msg carries
    /// PR_RTF_COMPRESSED like a natively-composed Outlook message.
    ///
    /// MsgKit's converter already maps a text/rtf body part onto Email.BodyRtf and
    /// compresses it on save - it just never fires, because Outlook for Mac writes
    /// text/plain and text/html and never text/rtf. Supplying that part is enough
    /// to light up the existing path.
    /// </summary>
    private static void AddRtfBody(MimeMessage message)
    {
        var bodyText = message.BodyParts.OfType<TextPart>().Where(p => !p.IsAttachment).ToList();

        // A message that already carries real RTF keeps it - never second-guess a
        // body the sender actually authored.
        if (bodyText.Any(p => p.IsRichText)) return;

        var html = bodyText.FirstOrDefault(p => p.IsHtml);

        // Plain-text-only mail gets no RTF: \fromhtml1 would be a lie, and Outlook
        // renders plain bodies correctly without it.
        if (html is null) return;

        var rtfPart = new TextPart("rtf") { Text = RtfEncapsulator.FromHtml(html.Text) };

        switch (message.Body)
        {
            case Multipart multipart:
                multipart.Add(rtfPart);
                break;
            case { } single:
                message.Body = new Multipart("alternative") { single, rtfPart };
                break;
        }
    }

    /// <summary>Expands folders into their .eml children; passes files through.</summary>
    private static List<string> ResolveInputs(IEnumerable<string> inputs, out List<string> badPaths)
    {
        var files = new List<string>();
        badPaths = [];

        foreach (var input in inputs)
        {
            var path = Path.GetFullPath(input);

            if (Directory.Exists(path))
                files.AddRange(Directory.EnumerateFiles(path, "*.eml", SearchOption.TopDirectoryOnly));
            else if (File.Exists(path))
                files.Add(path);
            else
                badPaths.Add(input);
        }

        return files.Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(f => f).ToList();
    }

    /// <summary>Appends " (n)" rather than clobbering an existing .msg.</summary>
    private static string MakeUnique(string path)
    {
        if (!File.Exists(path)) return path;

        var dir = Path.GetDirectoryName(path) ?? ".";
        var stem = Path.GetFileNameWithoutExtension(path);
        var ext = Path.GetExtension(path);

        for (var n = 1; n < 1000; n++)
        {
            var candidate = Path.Combine(dir, $"{stem} ({n}){ext}");
            if (!File.Exists(candidate)) return candidate;
        }

        return path;
    }

    private static void TryDelete(string path)
    {
        try
        {
            if (File.Exists(path)) File.Delete(path);
        }
        catch
        {
            // Best effort only - the real error is already being reported.
        }
    }

    private static void PrintUsage() => Console.WriteLine(
        """
        eml2msg - convert Outlook .eml files to Windows Outlook .msg

        Usage:
          eml2msg [options] <file-or-folder> [more...]

        Options:
          -o, --outdir DIR   write .msg files to DIR (default: beside the .eml)
          -f, --from ADDR    sender to use when the .eml has no From: header
                             (also read from $EML2MSG_FROM)
              --no-rtf       skip the RTF body (RTF is added by default)
              --overwrite    replace an existing .msg instead of adding " (1)"
          -h, --help         show this help

        Examples:
          eml2msg mail.eml
          eml2msg ~/Desktop/exported-mail
          eml2msg -o ~/Desktop/converted a.eml b.eml
          eml2msg --from "Andre Atkinson <andre@example.com>" sent.eml
        """);
}
