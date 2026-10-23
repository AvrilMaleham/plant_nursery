"""
Helpers for the integration tests that drive the site like a browser.

The tests read a page the way a person does: the words on it, the labelled
values, the rows of a table, the links and the pictures. They do not match
the HTML text itself, so changing a tag, a class, or the spacing in a template
does not break a test. Only a change to what the page says does.
"""

import re
from html.parser import HTMLParser

from flask.testing import FlaskClient

# A one-pixel PNG, used wherever a test uploads a plant photo.
PHOTO = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Tags that start a new line or box on screen. A space goes between the text
# either side of them, so "Stock" and "38" do not run together.
BLOCK_TAGS = {
    "address", "article", "aside", "br", "button", "dd", "div", "dl", "dt",
    "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "label",
    "li", "main", "nav", "ol", "p", "section", "table", "td", "th", "tr",
    "ul",
}
# Text inside these is not shown on the page.
HIDDEN_TAGS = {"option", "script", "style", "title"}
# Text inside these is collected on its own as well.
CAPTURED_TAGS = {"dd", "dt", "h2", "li", "td", "th"}


def tidy(text: str) -> str:
    """
    Collapse every run of whitespace to one space and trim the ends.

    :param text (str): Text with any spacing
    :return (str): The same words with single spaces
    """
    return " ".join(text.split())


class Section:
    """
    The part of a page under one h2 heading.

    :param text (str): The words in the section
    :param headers (list[str]): The column headings of its table, if any
    :param rows (list[list[str]]): The body rows of its table, cell by cell
    :param items (list[str]): The text of each list item
    """

    def __init__(self) -> None:
        """Start an empty section."""
        self.pieces: list[str] = []
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self.items: list[str] = []

    @property
    def text(self) -> str:
        """
        Get the words in the section.

        :return (str): The text, with single spaces
        """
        return tidy("".join(self.pieces))

    def __contains__(self, words: object) -> bool:
        """
        Check that some words appear in the section.

        :param words (object): The words to look for
        :return (bool): True if they are in the section text
        """
        return isinstance(words, str) and tidy(words) in self.text


class _Reader(HTMLParser):
    """Walk a page once and note down what a person could see on it."""

    def __init__(self) -> None:
        """Start reading with an empty page."""
        super().__init__()
        self.pieces: list[str] = []
        self.sections: dict[str, Section] = {"": Section()}
        self.definitions: dict[str, str] = {}
        self.images: list[str] = []
        self.links: list[str] = []
        self.__section = self.sections[""]
        self.__hidden = 0
        self.__open: dict[str, list[str]] = {}
        self.__term = ""
        self.__cells: list[str] = []
        self.__has_data_cell = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """
        Note a tag that opens.

        :param tag (str): The tag name
        :param attrs (list[tuple[str, str | None]]): Its attributes
        """
        attributes = dict(attrs)
        if tag in HIDDEN_TAGS:
            self.__hidden += 1
        if tag in BLOCK_TAGS:
            self.__add(" ")
        if tag in CAPTURED_TAGS:
            self.__open[tag] = []
        if tag == "tr":
            self.__cells = []
            self.__has_data_cell = False
        if tag == "td":
            self.__has_data_cell = True
        if tag == "img" and attributes.get("src"):
            self.images.append(attributes["src"] or "")
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"] or "")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """
        Note a tag that closes itself, such as br or img.

        :param tag (str): The tag name
        :param attrs (list[tuple[str, str | None]]): Its attributes
        """
        self.handle_starttag(tag, attrs)
        if tag not in CAPTURED_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        """
        Note a tag that closes.

        :param tag (str): The tag name
        """
        if tag in HIDDEN_TAGS and self.__hidden:
            self.__hidden -= 1
        if tag in BLOCK_TAGS:
            self.__add(" ")
        if tag in CAPTURED_TAGS and tag in self.__open:
            self.__finish(tag, tidy("".join(self.__open.pop(tag))))
        if tag == "tr" and self.__cells:
            if self.__has_data_cell:
                self.__section.rows.append(self.__cells)
            else:
                self.__section.headers = self.__cells
            self.__cells = []

    def handle_data(self, data: str) -> None:
        """
        Note some text between tags.

        :param data (str): The text, with entities already decoded
        """
        if not self.__hidden:
            self.__add(data)

    def __add(self, data: str) -> None:
        """
        Add text to the page, the section it is in, and any open element.

        :param data (str): The text
        """
        self.pieces.append(data)
        # A heading belongs to the section it opens, not the one it closes.
        if "h2" not in self.__open:
            self.__section.pieces.append(data)
        for pieces in self.__open.values():
            pieces.append(data)

    def __finish(self, tag: str, text: str) -> None:
        """
        Record an element whose text was captured.

        :param tag (str): The tag that closed
        :param text (str): Its text
        """
        if tag == "h2":
            self.__section = self.sections.setdefault(text, Section())
        elif tag == "dt":
            self.__term = text
        elif tag == "dd":
            self.definitions.setdefault(self.__term, text)
        elif tag == "li":
            self.__section.items.append(text)
        else:
            self.__cells.append(text)


class Page:
    """
    One page of the site, read the way a person reads it.

    Use `"some words" in page` to check the words shown, page.value("Stock")
    for a labelled value, and page.section("Most ordered").rows for a table.

    :param text (str): The words on the page
    :param definitions (dict[str, str]): Each label and the value beside it
    :param images (list[str]): The address of each picture
    :param links (list[str]): The address of each link
    """

    def __init__(self, html: str) -> None:
        """
        Read a page.

        :param html (str): The HTML the site returned
        """
        reader = _Reader()
        reader.feed(html)
        reader.close()
        self.text = tidy("".join(reader.pieces))
        self.definitions = reader.definitions
        self.images = reader.images
        self.links = reader.links
        self.__sections = reader.sections

    def __contains__(self, words: object) -> bool:
        """
        Check that some words appear on the page.

        :param words (object): The words to look for
        :return (bool): True if they are in the page text
        """
        return isinstance(words, str) and tidy(words) in self.text

    def value(self, label: str) -> str:
        """
        Get the value shown beside a label, such as Stock or Status.

        :param label (str): The label as shown on the page
        :return (str): The value beside it
        """
        assert label in self.definitions, (
            f"No '{label}' on the page. It shows: {sorted(self.definitions)}"
        )
        return self.definitions[label]

    def section(self, heading: str) -> Section:
        """
        Get the part of the page under a heading.

        :param heading (str): The heading text, such as Most ordered
        :return (Section): That part of the page
        """
        assert heading in self.__sections, (
            f"No '{heading}' heading. The headings are: "
            f"{[name for name in self.__sections if name]}"
        )
        return self.__sections[heading]

    def link_to(self, prefix: str) -> str:
        """
        Get the first link to a record, such as /orders/<id>.

        :param prefix (str): The start of the address, such as /orders
        :return (str): The address of the first matching link
        """
        pattern = re.compile(rf"^{re.escape(prefix)}/[0-9a-fA-F-]{{36}}$")
        found = [link for link in self.links if pattern.match(link)]
        assert found, f"No {prefix} link on the page. Links: {self.links}"
        return found[0]


def page(response: object) -> Page:
    """
    Read the page from a response that finished on a page.

    :param response (object): The response from the test client
    :return (Page): The page that came back
    """
    assert response.status_code == 200
    return Page(response.get_data(as_text=True))


def login(client: FlaskClient, username: str, password: str) -> Page:
    """
    Sign in through the login form.

    :param client (FlaskClient): The browser session
    :param username (str): Login name
    :param password (str): The password as typed
    :return (Page): The dashboard
    """
    response = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
    return page(response)


def logout(client: FlaskClient) -> None:
    """
    Sign out through the logout button.

    :param client (FlaskClient): The browser session
    """
    response = client.post("/logout", follow_redirects=True)
    assert response.status_code == 200


def record_id(path: str) -> str:
    """
    Return the id at the end of a page address.

    :param path (str): A path such as /plants/<id>
    :return (str): The id
    """
    return path.rstrip("/").rsplit("/", 1)[-1]


def referred_from(path: str) -> dict[str, str]:
    """
    Make the header a browser sends when a form is submitted from a page.

    A refused form sends the person back to this page.

    :param path (str): The page the form is on
    :return (dict[str, str]): Headers for the test client
    """
    return {"Referer": f"http://localhost{path}"}
