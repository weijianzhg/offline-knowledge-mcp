"""Publisher-specific provenance for the supported English ZIM collections."""
import re
from urllib.parse import quote, unquote

PROFILES = {
    "wikipedia": {
        "license": "Wikipedia text: CC BY-SA; see article attribution/history. Media licenses vary.",
        "license_url": "https://en.wikipedia.org/wiki/Wikipedia:Copyrights",
    },
    "wikivoyage": {
        "license": "Wikivoyage text: CC BY-SA; see page attribution/history. Media licenses vary.",
        "license_url": "https://en.wikivoyage.org/wiki/Wikivoyage:Copyleft",
    },
    "ifixit": {
        "license": "iFixit content: CC BY-NC-SA 3.0; retain attribution. See publisher licensing terms.",
        "license_url": "https://www.ifixit.com/Info/Licensing",
    },
    "gutenberg": {
        "license": "Project Gutenberg terms and per-book notices apply; copyright status varies by country.",
        "license_url": "https://www.gutenberg.org/policy/license.html",
    },
}


def citation_url(collection, path):
    path = path[2:] if path.startswith("A/") else path
    if collection in ("wikipedia", "wikivoyage"):
        return "https://en." + collection + ".org/wiki/" + quote(unquote(path), safe="_()/")
    if collection == "ifixit":
        return "https://www.ifixit.com/" + quote(unquote(path), safe="/+()_")
    if collection == "gutenberg":
        match = re.search(r"\.(\d+)$", path)
        if not match:
            raise ValueError("Gutenberg entry has no supported ebook identifier")
        return "https://www.gutenberg.org/ebooks/" + match.group(1)
    raise ValueError("Unsupported archive collection")
