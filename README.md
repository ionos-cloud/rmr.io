<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# RMR Documentation

Documentation site for the RMR project, built with [Sphinx](https://www.sphinx-doc.org/) and the [Alabaster](https://alabaster.readthedocs.io/) theme. All content is written in Markdown via [MyST Parser](https://myst-parser.readthedocs.io/).

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then install dependencies:

```bash
uv sync
```

In local development, start a live-reloading dev server:

```bash
uv run sphinx-autobuild docs docs/_build/html
```

Open http://127.0.0.1:8000 in your browser. Changes to `.md` files will auto-refresh.

To build the HTML without the dev server:

```bash
uv run sphinx-build -b html docs docs/_build/html
```

Output goes to `docs/_build/html/`.

## Adding Pages

1. Create a new `.md` file in the appropriate section directory (e.g. `docs/architecture/new-page.md`).
2. Add the filename (without extension) to the `toctree` in that section's `index.md`.

