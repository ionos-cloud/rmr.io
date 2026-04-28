# SPDX-FileCopyrightText: 2026 IONOS SE
# SPDX-License-Identifier: GPL-2.0-or-later

project = 'RMR and BRMR Documentation'
copyright = '2026, IONOS SE'
author = 'The RMR and BRMR developers'

# -- Extensions -----------------------------------------------------------
extensions = [
    'myst_parser',
]

# Allow both .rst and .md source files
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# MyST Parser extensions
myst_enable_extensions = [
    'strikethrough',
    'colon_fence',
]

# Generate anchor IDs for headings up to level 4 so intra-page #fragment links work
myst_heading_anchors = 4

# Automatically inject a local TOC at the top of every content page.
# Index pages (named "index") are skipped since they only contain toctrees.
def _inject_local_toc(app, docname, source):
    if docname.endswith('/index') or docname == 'index':
        return
    if '```{contents}' in source[0]:
        return
    import re
    toc_block = "\n```{contents}\n:local:\n:depth: 2\n```\n"
    # Insert after the first H1 heading line
    source[0] = re.sub(r'^(# .+\n)', r'\1' + toc_block, source[0], count=1, flags=re.MULTILINE)

def setup(app):
    app.connect('source-read', _inject_local_toc)

# Static files
html_static_path = ['_static']

# Theme overrides (e.g. sidebar navigation.html with a deeper toctree)
templates_path = ['_templates']

# -- Theme configuration --------------------------------------------------
html_theme = 'alabaster'

html_sidebars = {
    '**': [
        'about.html',
        'searchfield.html',
        'navigation.html',
        'relations.html',
    ]
}

html_theme_options = {
    'description': 'RMR and BRMR Project Documentation',
    'fixed_sidebar': True,
}
