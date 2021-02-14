from __future__ import annotations
import typing as t
import os
import requests

import dataclasses

import jinja2
import click


MARKDOWN_FILE_EXTENTION = ".md"
HTML_FILE_EXTENTION = ".html"
MARKDOWN_INDEX_FILE = f"__index__{MARKDOWN_FILE_EXTENTION}"
HTML_INDEX_FILE = f"__index__{HTML_FILE_EXTENTION}"
TEMPLATE_FILE_NAME = f"__template__{HTML_FILE_EXTENTION}"


class InvalidDirectoryTree(Exception):
    pass


@dataclasses.dataclass
class NavigationItem:
    path: str
    sub_items: t.List[NavigationItem]
    template: str
    root_dir: str

    def html_file_name(self):
        return (
            os.path.basename(self.path)[: -len(MARKDOWN_FILE_EXTENTION)]
            + HTML_FILE_EXTENTION
        )

    def html_file_path(self):
        return os.path.join(
            os.path.dirname(os.path.relpath(self.path, self.root_dir)),
            self.html_file_name(),
        )

    def html_file_directory(self):
        return os.path.dirname(self.html_file_path())

    def title(self):
        if self.is_navigation_parent():
            return self.directory_name()
        return os.path.basename(self.path)[: -len(MARKDOWN_FILE_EXTENTION)]

    def directory_name(self):
        return os.path.basename(os.path.dirname(self.path))

    @classmethod
    def local_template_file_maybe(cls, path: str, root_dir: str):
        possible_template_file = os.path.join(path, TEMPLATE_FILE_NAME)
        if os.path.isfile(possible_template_file):
            return os.path.relpath(possible_template_file, root_dir)

    @classmethod
    def from_path(cls, path: str, template=None, root_dir="") -> t.List[NavigationItem]:
        root_dir = root_dir or path
        template = cls.local_template_file_maybe(path, root_dir) or template
        if template is None:
            raise InvalidDirectoryTree("No root template file")

        items = []
        for object in sorted(os.listdir(path)):
            object_path = os.path.join(path, object)
            if cls.path_is_navigation_leaf(object_path):
                node = cls(object_path, [], template, root_dir)
            elif cls.path_is_navigation_dir(object_path):
                node = cls(
                    os.path.join(object_path, MARKDOWN_INDEX_FILE),
                    cls.from_path(object_path, template=template, root_dir=root_dir),
                    template,
                    root_dir,
                )
            else:
                continue
            items.append(node)

        return items

    def is_navigation_parent(self):
        return bool(self.sub_items)

    @staticmethod
    def path_is_navigation_dir(path: str):
        return os.path.isdir(path) and MARKDOWN_INDEX_FILE in os.listdir(path)

    @staticmethod
    def path_is_navigation_leaf(path: str):
        return (
            os.path.isfile(path)
            and path.endswith(MARKDOWN_FILE_EXTENTION)
            and not os.path.basename(path) == MARKDOWN_INDEX_FILE
        )


@dataclasses.dataclass
class PageBuilder:
    source_dir: str
    destination_dir: str

    def __post_init__(self) -> None:
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.source_dir)
        )
        self.navigation = NavigationItem.from_path(self.source_dir)

    def build_markdown(self, file_path: str) -> str:
        with open(file_path) as file_:
            text = file_.read()
        response = requests.post(
            "https://api.github.com/markdown",
            json={"text": text},
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        response.raise_for_status()
        return str(response.content, "utf-8")

    def build_page(
        self,
        navigation_item: NavigationItem,
        context: t.Dict[str, t.Any],
    ) -> str:
        sidebar = self.build_sidebar_for(navigation_item)
        content = self.build_markdown(navigation_item.path)
        return self.jinja_env.get_template(navigation_item.template).render(
            {**context, "content": content, "sidebar": sidebar}
        )

    def build_sidebar_for(
        self, requester_item: NavigationItem, root_items: t.List[NavigationItem] = None
    ):
        if root_items is None:
            root_items = self.navigation
        if not root_items:
            return []
        sidebar = [
            (
                item.title(),
                os.path.relpath(
                    item.html_file_path(), requester_item.html_file_directory()
                ),
                self.build_sidebar_for(item, item.sub_items),
            )
            for item in root_items
        ]
        return sidebar

    def build_pages_recursive(
        self,
        root_items: t.List[NavigationItem] = None,
        global_context: t.Dict[str, t.Any] = None,
    ) -> None:
        if root_items is None:
            root_items = self.navigation
        global_context = global_context or {}
        for item in root_items:
            page = self.build_page(item, global_context)
            html_file_path = os.path.join(self.destination_dir, item.html_file_path())
            os.makedirs(os.path.dirname(html_file_path), exist_ok=True)
            with open(html_file_path, "w") as file_:
                file_.write(page)
            if item.is_navigation_parent():
                self.build_pages_recursive(
                    item.sub_items,
                    global_context,
                )


@click.command()
@click.argument("source", type=click.Path())
@click.argument("destination")
def build(source: str, destination: str):
    PageBuilder(source, destination).build_pages_recursive()


if __name__ == "__main__":
    build()
