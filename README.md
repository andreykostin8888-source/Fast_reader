# Speed_read_for_Andrey

A reading app for scientific texts. It has paced reading (Glide, Fade, RSVP, Chunks, Sentence),
reading aloud, summaries (Long, Middle, Short), a podcast with an MP3 file, a library with folders,
and it opens texts from links (DOI, PubMed, PMC or a journal page).

This repository holds two versions of the same app:

| Version | Where | How to use it |
|---|---|---|
| Phone (Android) | `index.html` and the files beside it | open the address below in Chrome and install the app |
| Computer | `Speed_read_for_Andrey.html` | download the file and open it in Chrome or Edge |

## Phone (Android)

1. In Chrome on the phone, open **https://andreykostin8888-source.github.io/Fast_reader/**
2. Tap the menu (three dots), then **Install app** (or **Add to Home screen**).
3. The app **Speed read** is now on the home screen. After the first start it works without a network.
   Summaries, the podcast, the neural voice and links need a network.

- To open a PDF from another app (Files, Gmail, Drive): tap **Share**, then **Speed read**.
- To open a link from Chrome: tap **Share**, then **Speed read**.
- The button with two sliders at the top opens the controls. The Back button closes a panel or a window.

## Computer

- **One file, without a network:** open `Speed_read_for_Andrey.html` on GitHub, press
  **Download raw file**, then open the downloaded file in Chrome or Edge.
- **Online:** open the address above in Chrome or Edge on the computer. Chrome can also install it
  as an app (the install button in the address bar).
- **Free neural voice without a network:** the helper program `lectern_voice.py`.
  The app explains it in the window **Key and models**.

## Your data

This repository holds only the app. Your texts, your library, your podcasts and your OpenRouter key
stay in your browser on each device. They are not in this repository.
The phone app and the computer file keep separate libraries. To move texts and podcasts, use
**Backup** in the library on one device and **Restore** on the other device.

## Files

| File | What it is |
|---|---|
| `index.html` | the app; the same as the computer file, plus the parts for installing it |
| `manifest.webmanifest` | name, icons and share settings of the installed app |
| `sw.js` | keeps the app for use without a network, and takes files and links shared from other apps |
| `icon-192.png`, `icon-512.png`, `icon-maskable-512.png` | icons of the installed app |
| `Speed_read_for_Andrey.html` | the computer version: one file that works without a network |
| `lectern_voice.py` | the helper program for a free neural voice on a computer |
| `.nojekyll` | tells GitHub Pages to publish the files as they are |

## A new version

Replace the files with the new ones (**Add file**, then **Upload files**). The installed app on the
phone gets the new version by itself and shows a message.

## Code of other projects in the app

See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
