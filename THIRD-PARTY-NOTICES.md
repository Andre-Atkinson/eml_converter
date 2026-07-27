# Third-Party Notices

`eml2msg` is distributed as a self-contained binary that bundles the following
third-party components. Each remains under its own license, reproduced or
referenced below.

| Component | Version | License | Copyright |
| --- | --- | --- | --- |
| [MsgKit](https://github.com/Sicos1977/MsgKit) | 3.0.5 | MIT | (C) 2015-2026 Magic-Sessions (Kees van Spelde) |
| [MimeKit](https://www.mimekit.net/) | 4.17.0 | MIT | .NET Foundation and Contributors |
| [Bouncy Castle](https://www.bouncycastle.org/) | 2.6.2 | MIT | Copyright (c) 2000-2025 The Legion of the Bouncy Castle Inc. |
| [OpenMcdf](https://github.com/ironfede/openmcdf) | 3.1.4 | MPL-2.0 | Copyright (c) 2010-2026 Federico Blaseotto, Jeremy Powell |
| [System.Security.Cryptography.Pkcs](https://dot.net/) | 10.0.0 | MIT | (c) Microsoft Corporation |

MimeKit and System.Security.Cryptography.Pkcs are pulled in transitively by
MsgKit; Bouncy Castle is pulled in by MimeKit.

---

## MIT License

The following components are licensed under the MIT License, with the copyrights
listed in the table above:

- MsgKit
- MimeKit
- System.Security.Cryptography.Pkcs

```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Bouncy Castle License

Bouncy Castle (`BouncyCastle.Cryptography`) is distributed under its MIT-style
license, reproduced verbatim from the package:

```
Copyright (c) 2000-2025 The Legion of the Bouncy Castle Inc. (https://www.bouncycastle.org).
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sub license, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions: The above copyright notice and this
permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## Mozilla Public License 2.0

OpenMcdf 3.1.4 is licensed under the Mozilla Public License, Version 2.0
(MPL-2.0). It is bundled **unmodified**. Its Source Code Form is available at
<https://github.com/ironfede/openmcdf>, and the full text of the license is at
<https://www.mozilla.org/en-US/MPL/2.0/>.

```
This Source Code Form is subject to the terms of the Mozilla Public License,
v. 2.0. If a copy of the MPL was not distributed with this file, You can obtain
one at https://mozilla.org/MPL/2.0/.
```
