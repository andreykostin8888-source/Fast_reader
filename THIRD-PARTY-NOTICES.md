# Code of other projects in the app

Both HTML files (`index.html` and `Speed_read_for_Andrey.html`) contain these libraries,
unchanged, each in its own script block:

| Library | Version | License | Source |
|---|---|---|---|
| PDF.js (Mozilla), reads PDF files | 3.11.174 | Apache License 2.0 | https://github.com/mozilla/pdf.js |
| mammoth.js (Michael Williamson), reads DOCX files | 1.6.0 | BSD 2-Clause License | https://github.com/mwilliamson/mammoth.js |
| lamejs, makes MP3 files; a JavaScript form of LAME | 1.2.1 | GNU Lesser General Public License 3.0 (LGPL-3.0) | https://github.com/zhuker/lamejs, https://lame.sourceforge.io |

The full license texts are at the source addresses above.
lamejs is used as a separate, unchanged script block: you can replace it with another build of lamejs.
