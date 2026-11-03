# Add-ons

A few tools need a large extra part to work: a full web browser engine to show
web pages, or sound and video playback. Most teachers never open those tools,
so the parts are not in the normal install; they are optional **add-ons** you
can add from inside Staffroom, with no Terminal.

| Add-on | What it is for | Size |
| --- | --- | --- |
| **Web** | A full web browser engine, for tools that show web pages the way a browser does. | about 340 MB to download, 900 MB on disk |
| **Media** | Sound and video playback, for tools that play audio or video clips. | about 90 MB to download, 245 MB on disk |

The Web add-on includes everything in the Media add-on, so with Web installed
Media shows *Comes with Web*.

## Which tools need one

A tool that cannot work without an add-on is listed greyed in the sidebar,
with *add-on* at the end of its row; its tooltip says *Needs the Web add-on*.
It still opens: instead of the tool you see what the add-on is for, its size,
and an **Install** button. Tools that work without an add-on, less well, say
so in a line over the part that would be better with it, with the same
offer. Settings › Add-ons lists, for each add-on, the tools that use it.

## Installing one

1. Open **Settings › Add-ons** (or press *Install* on a tool that needs it).
2. Press **Install** on the add-on's row and confirm.
3. Keep working: the row shows the progress, and **Details** shows the
   installer's own messages. The Web add-on can take a few minutes on a slow
   network.
4. When it is done, Staffroom asks to restart. A running app cannot load a
   new add-on, so the tools that need it open after the restart.

**Remove** takes it away again (and frees the disk space); tools that need it
are greyed out until you install it again. If you try to quit while an add-on
is being installed, Staffroom finishes first and then closes.

How it installs depends on how Staffroom was installed, which it works out by
itself:

- **Installed with `uv tool install`** (the usual way): uv re-installs
  Staffroom from the same place it came from, with the add-on. Your settings,
  library and files are not touched. A copy that follows `main` comes back at
  the newest release.
- **Run from a git checkout** (the macOS launcher app): `uv sync` adds the
  add-on to the checkout's environment. `staff update` and *Update now* keep
  the add-ons you have; a plain `uv sync` in Terminal removes them (run
  `uv sync --extra web` instead).
- **Anything else** (a self-contained app bundle, pip into a virtual
  environment): Staffroom cannot add to itself, and the row's *Show how*
  gives the line to install Staffroom with uv instead, with the add-on.

From Terminal, the same installer is:

```bash
staff addons list
staff addons install web
staff addons remove web
```

## When it does not work

The card says what went wrong in one sentence:

| It says | What to do |
| --- | --- |
| *…this Mac could not reach the internet…* | Try again when it is online. |
| *This network blocked the download…* | A school proxy or web filter. Try at home, or ask IT to allow `pypi.org`, `files.pythonhosted.org` and `github.com`. |
| *There is not enough free space…* | Free some space; the Web add-on needs about 900 MB. |
| *The download took too long…* | Try again on a faster network. |
| *…could not start uv…* | Quit Staffroom and run the line shown in Terminal. |

A failed download changes nothing: uv fetches everything before it touches
your copy. After a change Staffroom checks that it still starts; if it does
not, it puts back the add-ons you had and says so.

## Privacy

Installing an add-on is the only time Staffroom downloads anything besides
asking GitHub which release is newest, and it happens only when you press
*Install*. It fetches the add-on's packages from the Python package index
(and, for a copy installed from GitHub, Staffroom itself from GitHub); nothing
about you or your files is sent. See [Privacy](privacy.md).
