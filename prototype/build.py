"""Inject dummy.json into template.html -> index.html (open it in a browser; deck.gl loads from jsDelivr)."""
import os
here = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(here, "template.html")).read()
d = open(os.path.join(here, "dummy.json")).read()
html = t.replace("/*__DATA__*/", d)
doc = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">' + html + "</body></html>"
open(os.path.join(here, "index.html"), "w").write(doc)
print("wrote prototype/index.html")
