# Third-party notices

BenchPress is distributed under the GNU Affero General Public License v3.0 only
(see [license.txt](license.txt)). It bundles and redistributes the third-party
components listed below, each under its own license.

**This file is generated — do not edit it by hand.** Regenerate it with
`./scripts/generate-third-party-notices.sh` whenever a dependency is added,
removed, or upgraded.

The full license text of every component is shipped alongside the component
itself: Python packages carry theirs in `env/lib/python*/site-packages/*.dist-info/`
inside the published container image, and JavaScript packages carry theirs in
`node_modules/*/LICENSE`. To produce a single bundle of the full texts, run
`pip-licenses --format=markdown --with-license-file` in the bench virtualenv.

Two things this file cannot see are documented by hand in
[docs/integration-notices.md](docs/integration-notices.md): the Frappe apps BenchPress integrates
with (razorpay_frappe, vpn_management), and the web fonts vendored under
`benchpress/public/fonts/` and `docs/fonts/`. Neither is dependency metadata, so neither appears
in the tables below.

## Python dependencies

| Name                     | Version     | License                                                                                                                                        | URL                                                                                           |
|--------------------------|-------------|------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| protobuf                 | 7.35.1      | 3-Clause BSD License                                                                                                                           | https://developers.google.com/protocol-buffers/                                               |
| asttokens                | 3.0.2       | Apache 2.0                                                                                                                                     | https://github.com/gristlabs/asttokens                                                        |
| PyPika                   | 0.48.9      | Apache Software License                                                                                                                        | https://github.com/kayak/pypika                                                               |
| bleach                   | 6.3.0       | Apache Software License                                                                                                                        | https://github.com/mozilla/bleach                                                             |
| distro                   | 1.9.0       | Apache Software License                                                                                                                        | https://github.com/python-distro/distro                                                       |
| google-api-core          | 2.33.0      | Apache Software License                                                                                                                        | https://github.com/googleapis/google-cloud-python/tree/main/packages/google-api-core          |
| google-api-python-client | 2.188.0     | Apache Software License                                                                                                                        | https://github.com/googleapis/google-api-python-client/                                       |
| google-auth              | 2.48.0      | Apache Software License                                                                                                                        | https://github.com/googleapis/google-auth-library-python                                      |
| google-auth-httplib2     | 0.4.0       | Apache Software License                                                                                                                        | https://github.com/googleapis/google-cloud-python/packages/google-auth-httplib2               |
| google-auth-oauthlib     | 1.2.4       | Apache Software License                                                                                                                        | https://github.com/GoogleCloudPlatform/google-auth-library-python-oauthlib                    |
| googleapis-common-protos | 1.75.0      | Apache Software License                                                                                                                        | https://github.com/googleapis/google-cloud-python/tree/main/packages/googleapis-common-protos |
| proto-plus               | 1.28.2      | Apache Software License                                                                                                                        | https://github.com/googleapis/google-cloud-python/tree/main/packages/proto-plus               |
| pyOpenSSL                | 26.0.0      | Apache Software License                                                                                                                        | https://pyopenssl.org/                                                                        |
| requests                 | 2.33.1      | Apache Software License                                                                                                                        | https://github.com/psf/requests                                                               |
| rsa                      | 4.9.1       | Apache Software License                                                                                                                        | https://stuvel.eu/rsa                                                                         |
| tenacity                 | 9.1.4       | Apache Software License                                                                                                                        | https://github.com/jd/tenacity                                                                |
| vobject                  | 0.9.9       | Apache Software License                                                                                                                        | UNKNOWN                                                                                       |
| zopfli                   | 0.4.3       | Apache Software License                                                                                                                        | https://github.com/fonttools/py-zopfli                                                        |
| python-dateutil          | 2.9.0.post0 | Apache Software License; BSD License                                                                                                           | https://github.com/dateutil/dateutil                                                          |
| docker                   | 7.2.0       | Apache-2.0                                                                                                                                     | https://github.com/docker/docker-py                                                           |
| phonenumbers             | 9.0.35      | Apache-2.0                                                                                                                                     | https://github.com/daviddrysdale/python-phonenumbers                                          |
| packaging                | 26.2        | Apache-2.0 OR BSD-2-Clause                                                                                                                     | https://github.com/pypa/packaging                                                             |
| cryptography             | 46.0.7      | Apache-2.0 OR BSD-3-Clause                                                                                                                     | https://github.com/pyca/cryptography                                                          |
| passlib                  | 1.7.4       | BSD                                                                                                                                            | https://passlib.readthedocs.io                                                                |
| uritemplate              | 4.2.0       | BSD 3-Clause OR Apache-2.0                                                                                                                     | https://uritemplate.readthedocs.org                                                           |
| Jinja2                   | 3.1.6       | BSD License                                                                                                                                    | https://github.com/pallets/jinja/                                                             |
| PyQRCode                 | 1.2.1       | BSD License                                                                                                                                    | https://github.com/mnooner256/pyqrcode                                                        |
| Whoosh                   | 2.7.4       | BSD License                                                                                                                                    | http://bitbucket.org/mchaput/whoosh                                                           |
| babel                    | 2.16.0      | BSD License                                                                                                                                    | https://babel.pocoo.org/                                                                      |
| bleach-allowlist         | 1.0.3       | BSD License                                                                                                                                    | https://github.com/yourcelf/bleach-allowlist.git                                              |
| cssselect2               | 0.9.0       | BSD License                                                                                                                                    | https://doc.courtbouillon.org/cssselect2/                                                     |
| gitdb                    | 4.0.12      | BSD License                                                                                                                                    | https://github.com/gitpython-developers/gitdb                                                 |
| ipython                  | 8.37.0      | BSD License                                                                                                                                    | https://ipython.org                                                                           |
| prompt_toolkit           | 3.0.52      | BSD License                                                                                                                                    | https://github.com/prompt-toolkit/python-prompt-toolkit                                       |
| psutil                   | 7.0.0       | BSD License                                                                                                                                    | https://github.com/giampaolo/psutil                                                           |
| pyasn1_modules           | 0.4.2       | BSD License                                                                                                                                    | https://github.com/pyasn1/pyasn1-modules                                                      |
| pydyf                    | 0.12.1      | BSD License                                                                                                                                    | https://www.courtbouillon.org/pydyf                                                           |
| requests-oauthlib        | 2.0.0       | BSD License                                                                                                                                    | https://github.com/requests/requests-oauthlib                                                 |
| semantic-version         | 2.10.0      | BSD License                                                                                                                                    | https://github.com/rbarrois/python-semanticversion                                            |
| sentry-sdk               | 1.45.1      | BSD License                                                                                                                                    | https://github.com/getsentry/sentry-python                                                    |
| smmap                    | 5.0.3       | BSD License                                                                                                                                    | https://github.com/gitpython-developers/smmap                                                 |
| sqlparse                 | 0.5.5       | BSD License                                                                                                                                    | https://github.com/andialbrecht/sqlparse                                                      |
| tinycss2                 | 1.5.1       | BSD License                                                                                                                                    | https://www.courtbouillon.org/tinycss2                                                        |
| traitlets                | 5.15.1      | BSD License                                                                                                                                    | https://github.com/ipython/traitlets                                                          |
| weasyprint               | 68.0        | BSD License                                                                                                                                    | https://weasyprint.org/                                                                       |
| webencodings             | 0.5.1       | BSD License                                                                                                                                    | https://github.com/SimonSapin/python-webencodings                                             |
| websockets               | 15.0.1      | BSD License                                                                                                                                    | https://github.com/python-websockets/websockets                                               |
| xlrd                     | 2.0.2       | BSD License                                                                                                                                    | http://www.python-excel.org/                                                                  |
| xlsxwriter               | 3.2.9       | BSD License                                                                                                                                    | https://github.com/jmcnamara/XlsxWriter                                                       |
| qrcode                   | 8.2         | BSD License; Other/Proprietary License                                                                                                         | https://github.com/lincolnloop/python-qrcode                                                  |
| Pygments                 | 2.20.0      | BSD-2-Clause                                                                                                                                   | https://pygments.org                                                                          |
| decorator                | 5.3.1       | BSD-2-Clause                                                                                                                                   | UNKNOWN                                                                                       |
| pyasn1                   | 0.6.4       | BSD-2-Clause                                                                                                                                   | https://github.com/pyasn1/pyasn1                                                              |
| rq                       | 2.6.1       | BSD-2-Clause                                                                                                                                   | https://python-rq.org/                                                                        |
| GitPython                | 3.1.57      | BSD-3-Clause                                                                                                                                   | https://github.com/gitpython-developers/GitPython                                             |
| MarkupSafe               | 3.0.3       | BSD-3-Clause                                                                                                                                   | https://github.com/pallets/markupsafe/                                                        |
| Werkzeug                 | 3.1.6       | BSD-3-Clause                                                                                                                                   | https://github.com/pallets/werkzeug/                                                          |
| click                    | 8.3.3       | BSD-3-Clause                                                                                                                                   | https://github.com/pallets/click/                                                             |
| cssselect                | 1.4.0       | BSD-3-Clause                                                                                                                                   | https://github.com/scrapy/cssselect                                                           |
| idna                     | 3.18        | BSD-3-Clause                                                                                                                                   | https://github.com/kjd/idna                                                                   |
| lxml                     | 6.1.1       | BSD-3-Clause                                                                                                                                   | https://lxml.de/                                                                              |
| matplotlib-inline        | 0.2.2       | BSD-3-Clause                                                                                                                                   | https://github.com/ipython/matplotlib-inline                                                  |
| oauthlib                 | 3.3.1       | BSD-3-Clause                                                                                                                                   | https://github.com/oauthlib/oauthlib                                                          |
| pycparser                | 3.0         | BSD-3-Clause                                                                                                                                   | https://github.com/eliben/pycparser                                                           |
| pypdf                    | 6.13.3      | BSD-3-Clause                                                                                                                                   | https://github.com/py-pdf/pypdf                                                               |
| mysqlclient              | 2.2.7       | GNU General Public License v2 or later (GPLv2+)                                                                                                | https://mysqlclient.readthedocs.io/                                                           |
| pyphen                   | 0.17.2      | GNU General Public License v2 or later (GPLv2+); GNU Lesser General Public License v2 or later (LGPLv2+); Mozilla Public License 1.1 (MPL 1.1) | https://www.courtbouillon.org/pyphen                                                          |
| pycountry                | 24.6.1      | GNU Lesser General Public License v2 (LGPLv2)                                                                                                  | https://github.com/flyingcircusio/pycountry                                                   |
| chardet                  | 5.2.0       | GNU Lesser General Public License v2 or later (LGPLv2+)                                                                                        | https://github.com/chardet/chardet                                                            |
| ldap3                    | 2.9.1       | GNU Lesser General Public License v3 (LGPLv3)                                                                                                  | https://github.com/cannatag/ldap3                                                             |
| cssutils                 | 2.11.1      | GNU Library or Lesser General Public License (LGPL)                                                                                            | https://github.com/jaraco/cssutils                                                            |
| num2words                | 0.5.14      | GNU Library or Lesser General Public License (LGPL)                                                                                            | https://github.com/savoirfairelinux/num2words                                                 |
| psycopg2-binary          | 2.9.12      | GNU Library or Lesser General Public License (LGPL)                                                                                            | https://psycopg.org/                                                                          |
| pexpect                  | 4.9.0       | ISC License (ISCL)                                                                                                                             | https://pexpect.readthedocs.io/                                                               |
| ptyprocess               | 0.7.0       | ISC License (ISCL)                                                                                                                             | https://github.com/pexpect/ptyprocess                                                         |
| PyJWT                    | 2.13.0      | MIT                                                                                                                                            | https://github.com/jpadilla/pyjwt                                                             |
| PyMySQL                  | 1.1.2       | MIT                                                                                                                                            | https://github.com/PyMySQL/PyMySQL/blob/main/CHANGELOG.md                                     |
| annotated-types          | 0.8.0       | MIT                                                                                                                                            | https://github.com/annotated-types/annotated-types                                            |
| brotli                   | 1.2.0       | MIT                                                                                                                                            | https://github.com/google/brotli                                                              |
| cachetools               | 7.1.6       | MIT                                                                                                                                            | https://github.com/tkem/cachetools/                                                           |
| charset-normalizer       | 3.4.9       | MIT                                                                                                                                            | https://github.com/jawah/charset_normalizer/blob/master/CHANGELOG.md                          |
| email-reply-parser       | 0.5.12      | MIT                                                                                                                                            | https://github.com/zapier/email-reply-parser                                                  |
| fonttools                | 4.63.0      | MIT                                                                                                                                            | http://github.com/fonttools/fonttools                                                         |
| markdown2                | 2.5.5       | MIT                                                                                                                                            | https://github.com/trentm/python-markdown2                                                    |
| more-itertools           | 11.1.0      | MIT                                                                                                                                            | https://github.com/more-itertools/more-itertools                                              |
| nh3                      | 0.3.6       | MIT                                                                                                                                            | UNKNOWN                                                                                       |
| pdfkit                   | 1.0.0       | MIT                                                                                                                                            | UNKNOWN                                                                                       |
| pydantic                 | 2.12.5      | MIT                                                                                                                                            | https://github.com/pydantic/pydantic                                                          |
| pydantic_core            | 2.41.5      | MIT                                                                                                                                            | https://github.com/pydantic/pydantic-core                                                     |
| pyparsing                | 3.3.2       | MIT                                                                                                                                            | https://github.com/pyparsing/pyparsing/                                                       |
| redis                    | 7.1.1       | MIT                                                                                                                                            | https://github.com/redis/redis-py                                                             |
| soupsieve                | 2.9.1       | MIT                                                                                                                                            | https://github.com/facelessuser/soupsieve                                                     |
| typing-inspection        | 0.4.2       | MIT                                                                                                                                            | https://github.com/pydantic/typing-inspection                                                 |
| urllib3                  | 2.7.0       | MIT                                                                                                                                            | https://github.com/urllib3/urllib3/blob/main/CHANGES.rst                                      |
| PyYAML                   | 6.0.3       | MIT License                                                                                                                                    | https://pyyaml.org/                                                                           |
| beautifulsoup4           | 4.13.5      | MIT License                                                                                                                                    | https://www.crummy.com/software/BeautifulSoup/bs4/                                            |
| croniter                 | 6.0.0       | MIT License                                                                                                                                    | http://github.com/kiorky/croniter                                                             |
| docopt                   | 0.6.2       | MIT License                                                                                                                                    | http://docopt.org                                                                             |
| duckdb                   | 1.4.5       | MIT License                                                                                                                                    | https://github.com/duckdb/duckdb-python                                                       |
| et_xmlfile               | 2.0.0       | MIT License                                                                                                                                    | https://foss.heptapod.net/openpyxl/et_xmlfile                                                 |
| executing                | 2.2.1       | MIT License                                                                                                                                    | https://github.com/alexmojaki/executing                                                       |
| filetype                 | 1.2.0       | MIT License                                                                                                                                    | https://github.com/h2non/filetype.py                                                          |
| gunicorn                 | 23.0.0      | MIT License                                                                                                                                    | https://gunicorn.org                                                                          |
| hiredis                  | 3.3.1       | MIT License                                                                                                                                    | https://github.com/redis/hiredis-py                                                           |
| html5lib                 | 1.1         | MIT License                                                                                                                                    | https://github.com/html5lib/html5lib-python                                                   |
| httplib2                 | 0.32.0      | MIT License                                                                                                                                    | https://github.com/httplib2/httplib2                                                          |
| jedi                     | 0.20.0      | MIT License                                                                                                                                    | https://github.com/davidhalter/jedi                                                           |
| markdownify              | 1.2.3       | MIT License                                                                                                                                    | http://github.com/matthewwithanm/python-markdownify                                           |
| openpyxl                 | 3.1.5       | MIT License                                                                                                                                    | https://openpyxl.readthedocs.io                                                               |
| parso                    | 0.8.7       | MIT License                                                                                                                                    | https://github.com/davidhalter/parso                                                          |
| pure_eval                | 0.2.3       | MIT License                                                                                                                                    | http://github.com/alexmojaki/pure_eval                                                        |
| pyotp                    | 2.9.0       | MIT License                                                                                                                                    | https://github.com/pyotp/pyotp                                                                |
| pytz                     | 2025.2      | MIT License                                                                                                                                    | http://pythonhosted.org/pytz                                                                  |
| rauth                    | 0.7.3       | MIT License                                                                                                                                    | https://github.com/litl/rauth                                                                 |
| six                      | 1.17.0      | MIT License                                                                                                                                    | https://github.com/benjaminp/six                                                              |
| sql_metadata             | 2.19.0      | MIT License                                                                                                                                    | https://github.com/macbre/sql-metadata                                                        |
| stack-data               | 0.6.3       | MIT License                                                                                                                                    | http://github.com/alexmojaki/stack_data                                                       |
| terminaltables           | 3.1.10      | MIT License                                                                                                                                    | https://github.com/matthewdeanmartin/terminaltables                                           |
| tinyhtml5                | 2.1.0       | MIT License                                                                                                                                    | https://github.com/CourtBouillon/tinyhtml5                                                    |
| traceback-with-variables | 2.2.1       | MIT License                                                                                                                                    | https://github.com/andy-landy/traceback_with_variables                                        |
| zxcvbn                   | 4.5.0       | MIT License                                                                                                                                    | https://github.com/dwolfhub/zxcvbn-python                                                     |
| cffi                     | 2.1.0       | MIT-0                                                                                                                                          | https://cffi.readthedocs.io/en/latest/whatsnew.html                                           |
| pillow                   | 12.2.0      | MIT-CMU                                                                                                                                        | https://python-pillow.github.io                                                               |
| orjson                   | 3.11.9      | MPL-2.0 AND (Apache-2.0 OR MIT)                                                                                                                | https://github.com/ijl/orjson                                                                 |
| certifi                  | 2026.7.22   | Mozilla Public License 2.0 (MPL 2.0)                                                                                                           | https://github.com/certifi/python-certifi                                                     |
| typing_extensions        | 4.16.0      | PSF-2.0                                                                                                                                        | https://github.com/python/typing_extensions                                                   |
| premailer                | 3.10.0      | Python Software Foundation License                                                                                                             | http://github.com/peterbe/premailer                                                           |
| frappe                   | 16.28.0     | UNKNOWN                                                                                                                                        | https://frappe.io/framework                                                                   |
| filelock                 | 3.20.4      | Unlicense                                                                                                                                      | https://github.com/tox-dev/py-filelock                                                        |
| RestrictedPython         | 8.4         | ZPL-2.1                                                                                                                                        | https://github.com/zopefoundation/RestrictedPython                                            |

## JavaScript dependencies (frontend, production only)

- [@alloc/quick-lru@5.2.0](https://github.com/sindresorhus/quick-lru) - MIT
- [@antfu/install-pkg@1.1.0](https://github.com/antfu/install-pkg) - MIT
- [@babel/helper-string-parser@7.27.1](https://github.com/babel/babel) - MIT
- [@babel/helper-validator-identifier@7.28.5](https://github.com/babel/babel) - MIT
- [@babel/parser@7.29.2](https://github.com/babel/babel) - MIT
- [@babel/types@7.29.0](https://github.com/babel/babel) - MIT
- [@floating-ui/core@1.7.5](https://github.com/floating-ui/floating-ui) - MIT
- [@floating-ui/dom@1.7.6](https://github.com/floating-ui/floating-ui) - MIT
- [@floating-ui/utils@0.2.11](https://github.com/floating-ui/floating-ui) - MIT
- [@floating-ui/vue@1.1.11](https://github.com/floating-ui/floating-ui) - MIT
- [@headlessui/vue@1.7.23](https://github.com/tailwindlabs/headlessui) - MIT
- [@iconify/types@2.0.0](https://github.com/iconify/iconify) - MIT
- [@iconify/utils@3.1.0](https://github.com/iconify/iconify) - MIT
- [@interactjs/types@1.10.27](https://github.com/taye/interact.js) - MIT
- [@internationalized/date@3.12.0](https://github.com/adobe/react-spectrum.git#main) - Apache-2.0
- [@internationalized/number@3.6.5](https://github.com/adobe/react-spectrum) - Apache-2.0
- [@jridgewell/gen-mapping@0.3.13](https://github.com/jridgewell/sourcemaps) - MIT
- [@jridgewell/remapping@2.3.5](https://github.com/jridgewell/sourcemaps) - MIT
- [@jridgewell/resolve-uri@3.1.2](https://github.com/jridgewell/resolve-uri) - MIT
- [@jridgewell/sourcemap-codec@1.5.5](https://github.com/jridgewell/sourcemaps) - MIT
- [@jridgewell/trace-mapping@0.3.31](https://github.com/jridgewell/sourcemaps) - MIT
- [@juggle/resize-observer@3.4.0](https://github.com/juggle/resize-observer) - Apache-2.0
- [@nodelib/fs.scandir@2.1.5](https://github.com/nodelib/nodelib.git#master) - MIT
- [@nodelib/fs.stat@2.0.5](https://github.com/nodelib/nodelib.git#master) - MIT
- [@nodelib/fs.walk@1.2.8](https://github.com/nodelib/nodelib.git#master) - MIT
- [@popperjs/core@2.11.8](https://github.com/popperjs/popper-core) - MIT
- [@remirror/core-constants@3.0.0](https://github.com/remirror/remirror) - MIT
- [@socket.io/component-emitter@3.1.2](https://github.com/socketio/emitter) - MIT
- [@swc/helpers@0.5.19](https://github.com/swc-project/swc) - Apache-2.0
- [@tailwindcss/forms@0.5.11](https://github.com/tailwindlabs/tailwindcss-forms) - MIT
- [@tailwindcss/line-clamp@0.4.4](https://github.com/tailwindlabs/tailwindcss-line-clamp) - MIT
- [@tailwindcss/typography@0.5.19](https://github.com/tailwindlabs/tailwindcss-typography) - MIT
- [@tanstack/virtual-core@3.13.23](https://github.com/TanStack/virtual) - MIT
- [@tanstack/vue-virtual@3.13.23](https://github.com/TanStack/virtual) - MIT
- [@tiptap/core@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-blockquote@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-bold@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-bubble-menu@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-bullet-list@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-code-block-lowlight@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-code-block@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-code@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-color@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-document@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-dropcursor@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-floating-menu@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-gapcursor@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-hard-break@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-heading@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-highlight@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-horizontal-rule@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-image@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-italic@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-link@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-list-item@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-list-keymap@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-list@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-mention@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-node-range@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-ordered-list@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-paragraph@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-placeholder@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-strike@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-table@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-task-item@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-task-list@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-text-align@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-text-style@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-text@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-typography@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extension-underline@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/extensions@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/pm@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/starter-kit@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/suggestion@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@tiptap/vue-3@3.20.5](https://github.com/ueberdosis/tiptap) - MIT
- [@types/estree@1.0.8](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/hast@3.0.4](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/linkify-it@5.0.0](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/markdown-it@14.1.2](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/mdurl@2.0.0](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/trusted-types@2.0.7](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/unist@3.0.3](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/web-bluetooth@0.0.20](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@types/web-bluetooth@0.0.21](https://github.com/DefinitelyTyped/DefinitelyTyped) - MIT
- [@vexip-ui/hooks@2.9.3](https://github.com/vexip-ui/vexip-ui) - MIT
- [@vexip-ui/utils@2.16.4](https://github.com/vexip-ui/vexip-ui) - MIT
- [@vue/compiler-core@3.5.31](https://github.com/vuejs/core) - MIT
- [@vue/compiler-dom@3.5.31](https://github.com/vuejs/core) - MIT
- [@vue/compiler-sfc@3.5.31](https://github.com/vuejs/core) - MIT
- [@vue/compiler-ssr@3.5.31](https://github.com/vuejs/core) - MIT
- [@vue/devtools-api@6.6.4](https://github.com/vuejs/vue-devtools) - MIT
- [@vue/reactivity@3.5.31](https://github.com/vuejs/core) - MIT
- [@vue/runtime-core@3.5.31](https://github.com/vuejs/core) - MIT
- [@vue/runtime-dom@3.5.31](https://github.com/vuejs/core) - MIT
- [@vue/server-renderer@3.5.31](https://github.com/vuejs/core) - MIT
- [@vue/shared@3.5.31](https://github.com/vuejs/core) - MIT
- [@vueuse/core@10.11.1](https://github.com/vueuse/vueuse) - MIT
- [@vueuse/core@14.2.1](https://github.com/vueuse/vueuse) - MIT
- [@vueuse/metadata@10.11.1](https://github.com/vueuse/vueuse) - MIT
- [@vueuse/metadata@14.2.1](https://github.com/vueuse/vueuse) - MIT
- [@vueuse/shared@10.11.1](https://github.com/vueuse/vueuse) - MIT
- [@vueuse/shared@14.2.1](https://github.com/vueuse/vueuse) - MIT
- [acorn@8.16.0](https://github.com/acornjs/acorn) - MIT
- [ansi-regex@5.0.1](https://github.com/chalk/ansi-regex) - MIT
- [ansi-styles@4.3.0](https://github.com/chalk/ansi-styles) - MIT
- [any-promise@1.3.0](https://github.com/kevinbeaty/any-promise) - MIT
- [anymatch@3.1.3](https://github.com/micromatch/anymatch) - ISC
- [arg@5.0.2](https://github.com/vercel/arg) - MIT
- [argparse@2.0.1](https://github.com/nodeca/argparse) - Python-2.0
- [aria-hidden@1.2.6](https://github.com/theKashey/aria-hidden) - MIT
- [base64-js@1.5.1](https://github.com/beatgammit/base64-js) - MIT
- [binary-extensions@2.3.0](https://github.com/sindresorhus/binary-extensions) - MIT
- [bl@4.1.0](https://github.com/rvagg/bl) - MIT
- [braces@3.0.3](https://github.com/micromatch/braces) - MIT
- [buffer@5.7.1](https://github.com/feross/buffer) - MIT
- [camelcase-css@2.0.1](https://github.com/stevenvachon/camelcase-css) - MIT
- [camelcase@5.3.1](https://github.com/sindresorhus/camelcase) - MIT
- [chalk@4.1.2](https://github.com/chalk/chalk) - MIT
- [chokidar@3.6.0](https://github.com/paulmillr/chokidar) - MIT
- [classnames@2.5.1](https://github.com/JedWatson/classnames) - MIT
- [cli-cursor@3.1.0](https://github.com/sindresorhus/cli-cursor) - MIT
- [cli-spinners@2.9.2](https://github.com/sindresorhus/cli-spinners) - MIT
- [cliui@6.0.0](https://github.com/yargs/cliui) - ISC
- [clone@1.0.4](https://github.com/pvorb/node-clone) - MIT
- [color-convert@2.0.1](https://github.com/Qix-/color-convert) - MIT
- [color-name@1.1.4](https://github.com/colorjs/color-name) - MIT
- [commander@4.1.1](https://github.com/tj/commander.js) - MIT
- [confbox@0.1.8](https://github.com/unjs/confbox) - MIT
- [confbox@0.2.4](https://github.com/unjs/confbox) - MIT
- [core-js@3.49.0](https://github.com/zloirock/core-js) - MIT
- [crelt@1.0.6](https://github.com/marijnh/crelt) - MIT
- [cssesc@3.0.0](https://github.com/mathiasbynens/cssesc) - MIT
- [csstype@3.2.3](https://github.com/frenic/csstype) - MIT
- [dayjs@1.11.20](https://github.com/iamkun/dayjs) - MIT
- [debug@4.4.3](https://github.com/debug-js/debug) - MIT
- [decamelize@1.2.0](https://github.com/sindresorhus/decamelize) - MIT
- [defaults@1.0.4](https://github.com/sindresorhus/node-defaults) - MIT
- [defu@6.1.4](https://github.com/unjs/defu) - MIT
- [dequal@2.0.3](https://github.com/lukeed/dequal) - MIT
- [devlop@1.1.0](https://github.com/wooorm/devlop) - MIT
- [didyoumean@1.2.2](https://github.com/dcporter/didyoumean.js) - Apache-2.0
- [dijkstrajs@1.0.3](https://github.com/tcort/dijkstrajs) - MIT
- [dlv@1.1.3](https://github.com/developit/dlv) - MIT
- [dompurify@3.3.3](https://github.com/cure53/DOMPurify) - (MPL-2.0 OR Apache-2.0)
- [echarts@5.6.0](https://github.com/apache/echarts) - Apache-2.0
- [emoji-regex@8.0.0](https://github.com/mathiasbynens/emoji-regex) - MIT
- [engine.io-client@6.6.4](https://github.com/socketio/socket.io) - MIT
- [engine.io-parser@5.2.3](https://github.com/socketio/socket.io) - MIT
- [entities@4.5.0](https://github.com/fb55/entities) - BSD-2-Clause
- [entities@7.0.1](https://github.com/fb55/entities) - BSD-2-Clause
- [escape-string-regexp@4.0.0](https://github.com/sindresorhus/escape-string-regexp) - MIT
- [escape-string-regexp@5.0.0](https://github.com/sindresorhus/escape-string-regexp) - MIT
- [estree-walker@2.0.2](https://github.com/Rich-Harris/estree-walker) - MIT
- [estree-walker@3.0.3](https://github.com/Rich-Harris/estree-walker) - MIT
- [exsolve@1.0.8](https://github.com/unjs/exsolve) - MIT
- [fast-deep-equal@3.1.3](https://github.com/epoberezkin/fast-deep-equal) - MIT
- [fast-glob@3.3.3](https://github.com/mrmlnc/fast-glob) - MIT
- [fastq@1.20.1](https://github.com/mcollina/fastq) - ISC
- [fdir@6.5.0](https://github.com/thecodrr/fdir) - MIT
- [feather-icons@4.29.2](https://github.com/feathericons/feather) - MIT
- [fill-range@7.1.1](https://github.com/jonschlinkert/fill-range) - MIT
- [find-up@4.1.0](https://github.com/sindresorhus/find-up) - MIT
- [frappe-ui@0.1.278](https://github.com/frappe/frappe-ui) - MIT
- [function-bind@1.1.2](https://github.com/Raynos/function-bind) - MIT
- [get-caller-file@2.0.5](https://github.com/stefanpenner/get-caller-file) - ISC
- [glob-parent@5.1.2](https://github.com/gulpjs/glob-parent) - ISC
- [glob-parent@6.0.2](https://github.com/gulpjs/glob-parent) - ISC
- [grid-layout-plus@1.1.1](undefined) - MIT
- [has-flag@4.0.0](https://github.com/sindresorhus/has-flag) - MIT
- [hasown@2.0.2](https://github.com/inspect-js/hasOwn) - MIT
- [highlight.js@11.11.1](https://github.com/highlightjs/highlight.js) - BSD-3-Clause
- [idb-keyval@6.2.2](https://github.com/jakearchibald/idb-keyval) - Apache-2.0
- [ieee754@1.2.1](https://github.com/feross/ieee754) - BSD-3-Clause
- [inherits@2.0.4](https://github.com/isaacs/inherits) - ISC
- [interactjs@1.10.27](https://github.com/taye/interact.js) - MIT
- [is-binary-path@2.1.0](https://github.com/sindresorhus/is-binary-path) - MIT
- [is-core-module@2.16.1](https://github.com/inspect-js/is-core-module) - MIT
- [is-extglob@2.1.1](https://github.com/jonschlinkert/is-extglob) - MIT
- [is-fullwidth-code-point@3.0.0](https://github.com/sindresorhus/is-fullwidth-code-point) - MIT
- [is-glob@4.0.3](https://github.com/micromatch/is-glob) - MIT
- [is-interactive@1.0.0](https://github.com/sindresorhus/is-interactive) - MIT
- [is-number@7.0.0](https://github.com/jonschlinkert/is-number) - MIT
- [is-unicode-supported@0.1.0](https://github.com/sindresorhus/is-unicode-supported) - MIT
- [jiti@1.21.7](https://github.com/unjs/jiti) - MIT
- [js-tokens@9.0.1](https://github.com/lydell/js-tokens) - MIT
- [lilconfig@3.1.3](https://github.com/antonk52/lilconfig) - MIT
- [lines-and-columns@1.2.4](https://github.com/eventualbuddha/lines-and-columns) - MIT
- [linkify-it@5.0.0](https://github.com/markdown-it/linkify-it) - MIT
- [linkifyjs@4.3.2](https://github.com/nfrasser/linkifyjs) - MIT
- [local-pkg@1.1.2](https://github.com/antfu-collective/local-pkg) - MIT
- [locate-path@5.0.0](https://github.com/sindresorhus/locate-path) - MIT
- [log-symbols@4.1.0](https://github.com/sindresorhus/log-symbols) - MIT
- [lowlight@3.3.0](https://github.com/wooorm/lowlight) - MIT
- [lucide-static@0.545.0](https://github.com/lucide-icons/lucide) - ISC
- [magic-string@0.30.21](https://github.com/Rich-Harris/magic-string) - MIT
- [markdown-it@14.1.1](https://github.com/markdown-it/markdown-it) - MIT
- [marked@15.0.12](https://github.com/markedjs/marked) - MIT
- [mdurl@2.0.0](https://github.com/markdown-it/mdurl) - MIT
- [merge2@1.4.1](https://github.com/teambition/merge2) - MIT
- [micromatch@4.0.8](https://github.com/micromatch/micromatch) - MIT
- [mimic-fn@2.1.0](https://github.com/sindresorhus/mimic-fn) - MIT
- [mini-svg-data-uri@1.4.4](https://github.com/tigt/mini-svg-data-uri) - MIT
- [mlly@1.8.2](https://github.com/unjs/mlly) - MIT
- [ms@2.1.3](https://github.com/vercel/ms) - MIT
- [mz@2.7.0](https://github.com/normalize/mz) - MIT
- [nanoid@3.3.11](https://github.com/ai/nanoid) - MIT
- [nanoid@5.1.7](https://github.com/ai/nanoid) - MIT
- [normalize-path@3.0.0](https://github.com/jonschlinkert/normalize-path) - MIT
- [object-assign@4.1.1](https://github.com/sindresorhus/object-assign) - MIT
- [object-hash@3.0.0](https://github.com/puleos/object-hash) - MIT
- [ohash@2.0.11](https://github.com/unjs/ohash) - MIT
- [onetime@5.1.2](https://github.com/sindresorhus/onetime) - MIT
- [ora@5.4.1](https://github.com/sindresorhus/ora) - MIT
- [orderedmap@2.1.1](https://github.com/marijnh/orderedmap) - MIT
- [p-limit@2.3.0](https://github.com/sindresorhus/p-limit) - MIT
- [p-locate@4.1.0](https://github.com/sindresorhus/p-locate) - MIT
- [p-try@2.2.0](https://github.com/sindresorhus/p-try) - MIT
- [package-manager-detector@1.6.0](https://github.com/antfu-collective/package-manager-detector) - MIT
- [path-exists@4.0.0](https://github.com/sindresorhus/path-exists) - MIT
- [path-parse@1.0.7](https://github.com/jbgutierrez/path-parse) - MIT
- [pathe@2.0.3](https://github.com/unjs/pathe) - MIT
- [picocolors@1.1.1](https://github.com/alexeyraspopov/picocolors) - ISC
- [picomatch@2.3.2](https://github.com/micromatch/picomatch) - MIT
- [picomatch@4.0.4](https://github.com/micromatch/picomatch) - MIT
- [pify@2.3.0](https://github.com/sindresorhus/pify) - MIT
- [pirates@4.0.7](https://github.com/danez/pirates) - MIT
- [pkg-types@1.3.1](https://github.com/unjs/pkg-types) - MIT
- [pkg-types@2.3.0](https://github.com/unjs/pkg-types) - MIT
- [pngjs@5.0.0](https://github.com/lukeapage/pngjs) - MIT
- [postcss-import@15.1.0](https://github.com/postcss/postcss-import) - MIT
- [postcss-js@4.1.0](https://github.com/postcss/postcss-js) - MIT
- [postcss-load-config@6.0.1](https://github.com/postcss/postcss-load-config) - MIT
- [postcss-nested@6.2.0](https://github.com/postcss/postcss-nested) - MIT
- [postcss-selector-parser@6.0.10](https://github.com/postcss/postcss-selector-parser) - MIT
- [postcss-selector-parser@6.1.2](https://github.com/postcss/postcss-selector-parser) - MIT
- [postcss-value-parser@4.2.0](https://github.com/TrySound/postcss-value-parser) - MIT
- [postcss@8.5.8](https://github.com/postcss/postcss) - MIT
- [prettier@3.8.1](https://github.com/prettier/prettier) - MIT
- [prosemirror-changeset@2.4.0](https://github.com/prosemirror/prosemirror-changeset) - MIT
- [prosemirror-collab@1.3.1](https://github.com/prosemirror/prosemirror-collab) - MIT
- [prosemirror-commands@1.7.1](https://github.com/prosemirror/prosemirror-commands) - MIT
- [prosemirror-dropcursor@1.8.2](https://github.com/prosemirror/prosemirror-dropcursor) - MIT
- [prosemirror-gapcursor@1.4.1](https://github.com/prosemirror/prosemirror-gapcursor) - MIT
- [prosemirror-history@1.5.0](https://github.com/prosemirror/prosemirror-history) - MIT
- [prosemirror-inputrules@1.5.1](https://github.com/prosemirror/prosemirror-inputrules) - MIT
- [prosemirror-keymap@1.2.3](https://github.com/prosemirror/prosemirror-keymap) - MIT
- [prosemirror-markdown@1.13.4](https://github.com/prosemirror/prosemirror-markdown) - MIT
- [prosemirror-menu@1.3.0](https://github.com/prosemirror/prosemirror-menu) - MIT
- [prosemirror-model@1.25.4](https://github.com/prosemirror/prosemirror-model) - MIT
- [prosemirror-schema-basic@1.2.4](https://github.com/prosemirror/prosemirror-schema-basic) - MIT
- [prosemirror-schema-list@1.5.1](https://github.com/prosemirror/prosemirror-schema-list) - MIT
- [prosemirror-state@1.4.4](https://github.com/prosemirror/prosemirror-state) - MIT
- [prosemirror-tables@1.8.5](https://github.com/ProseMirror/prosemirror-tables) - MIT
- [prosemirror-trailing-node@3.0.0](https://github.com/remirror/remirror) - MIT
- [prosemirror-transform@1.11.0](https://github.com/prosemirror/prosemirror-transform) - MIT
- [prosemirror-view@1.41.7](https://github.com/prosemirror/prosemirror-view) - MIT
- [punycode.js@2.3.1](https://github.com/mathiasbynens/punycode.js) - MIT
- [qrcode@1.5.4](https://github.com/soldair/node-qrcode) - MIT
- [quansync@0.2.11](https://github.com/quansync-dev/quansync) - MIT
- [queue-microtask@1.2.3](https://github.com/feross/queue-microtask) - MIT
- [radix-vue@1.9.17](https://github.com/unovue/radix-vue) - MIT
- [read-cache@1.0.0](https://github.com/TrySound/read-cache) - MIT
- [readable-stream@3.6.2](https://github.com/nodejs/readable-stream) - MIT
- [readdirp@3.6.0](https://github.com/paulmillr/readdirp) - MIT
- [reka-ui@2.9.2](https://github.com/unovue/reka-ui) - MIT
- [require-directory@2.1.1](https://github.com/troygoode/node-require-directory) - MIT
- [require-main-filename@2.0.0](https://github.com/yargs/require-main-filename) - ISC
- [resolve@1.22.11](https://github.com/browserify/resolve) - MIT
- [restore-cursor@3.1.0](https://github.com/sindresorhus/restore-cursor) - MIT
- [reusify@1.1.0](https://github.com/mcollina/reusify) - MIT
- [rope-sequence@1.3.4](https://github.com/marijnh/rope-sequence) - MIT
- [run-parallel@1.2.0](https://github.com/feross/run-parallel) - MIT
- [safe-buffer@5.2.1](https://github.com/feross/safe-buffer) - MIT
- [scule@1.3.0](https://github.com/unjs/scule) - MIT
- [set-blocking@2.0.0](https://github.com/yargs/set-blocking) - ISC
- [signal-exit@3.0.7](https://github.com/tapjs/signal-exit) - ISC
- [slugify@1.6.8](https://github.com/simov/slugify) - MIT
- [socket.io-client@4.8.3](https://github.com/socketio/socket.io) - MIT
- [socket.io-parser@4.2.6](https://github.com/socketio/socket.io) - MIT
- [source-map-js@1.2.1](https://github.com/7rulnik/source-map-js) - BSD-3-Clause
- [string-width@4.2.3](https://github.com/sindresorhus/string-width) - MIT
- [string_decoder@1.3.0](https://github.com/nodejs/string_decoder) - MIT
- [strip-ansi@6.0.1](https://github.com/chalk/strip-ansi) - MIT
- [strip-literal@3.1.0](https://github.com/antfu/strip-literal) - MIT
- [sucrase@3.35.1](https://github.com/alangpierce/sucrase) - MIT
- [supports-color@7.2.0](https://github.com/chalk/supports-color) - MIT
- [supports-preserve-symlinks-flag@1.0.0](https://github.com/inspect-js/node-supports-preserve-symlinks-flag) - MIT
- [tailwindcss@3.4.19](https://github.com/tailwindlabs/tailwindcss.git#v3) - MIT
- [thenify-all@1.6.0](https://github.com/thenables/thenify-all) - MIT
- [thenify@3.3.1](https://github.com/thenables/thenify) - MIT
- [tinyexec@1.0.4](https://github.com/tinylibs/tinyexec) - MIT
- [tinyglobby@0.2.15](https://github.com/SuperchupuDev/tinyglobby) - MIT
- [tippy.js@6.3.7](https://github.com/atomiks/tippyjs) - MIT
- [to-regex-range@5.0.1](https://github.com/micromatch/to-regex-range) - MIT
- [ts-interface-checker@0.1.13](https://github.com/gristlabs/ts-interface-checker) - Apache-2.0
- [tslib@2.3.0](https://github.com/Microsoft/tslib) - 0BSD
- [tslib@2.8.1](https://github.com/Microsoft/tslib) - 0BSD
- [typescript@5.9.3](https://github.com/microsoft/TypeScript) - Apache-2.0
- [uc.micro@2.1.0](https://github.com/markdown-it/uc.micro) - MIT
- [ufo@1.6.3](https://github.com/unjs/ufo) - MIT
- [unimport@4.2.0](https://github.com/unjs/unimport) - MIT
- [unplugin-auto-import@19.3.0](https://github.com/unplugin/unplugin-auto-import) - MIT
- [unplugin-icons@22.5.0](https://github.com/unplugin/unplugin-icons) - MIT
- [unplugin-utils@0.2.5](https://github.com/sxzz/unplugin-utils) - MIT
- [unplugin-vue-components@28.8.0](https://github.com/unplugin/unplugin-vue-components) - MIT
- [unplugin@2.3.11](https://github.com/unjs/unplugin) - MIT
- [util-deprecate@1.0.2](https://github.com/TooTallNate/util-deprecate) - MIT
- [vue-demi@0.14.10](https://github.com/antfu/vue-demi) - MIT
- [vue-router@4.6.4](https://github.com/vuejs/router) - MIT
- [vue@3.5.31](https://github.com/vuejs/core) - MIT
- [w3c-keyname@2.2.8](https://github.com/marijnh/w3c-keyname) - MIT
- [wcwidth@1.0.1](https://github.com/timoxley/wcwidth) - MIT
- [webpack-virtual-modules@0.6.2](https://github.com/sysgears/webpack-virtual-modules) - MIT
- [which-module@2.0.1](https://github.com/nexdrew/which-module) - ISC
- [wrap-ansi@6.2.0](https://github.com/chalk/wrap-ansi) - MIT
- [ws@8.18.3](https://github.com/websockets/ws) - MIT
- [xmlhttprequest-ssl@2.1.2](https://github.com/mjwwit/node-XMLHttpRequest) - MIT
- [y18n@4.0.3](https://github.com/yargs/y18n) - ISC
- [yargs-parser@18.1.3](https://github.com/yargs/yargs-parser) - ISC
- [yargs@15.4.1](https://github.com/yargs/yargs) - MIT
- [zrender@5.6.1](https://github.com/ecomfe/zrender) - BSD-3-Clause


## Metadata corrections

The tables above report what each package publishes in its own metadata. Two
upstreams publish something incomplete or misleading; the authoritative license
is the one in the license file each of them actually ships.

| Package | Reported above | Actual license | Source |
|---|---|---|---|
| `frappe` | UNKNOWN — publishes no license metadata | MIT | `apps/frappe/LICENSE` |
| `qrcode` | `BSD License; Other/Proprietary License` | BSD 3-Clause | `qrcode-*.dist-info/LICENSE` |
