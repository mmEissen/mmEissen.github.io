from __future__ import annotations
import typing as t
import os
import requests
from requests import auth
import shutil

import functools

import dataclasses

import jinja2
import click


MARKDOWN_FILE_EXTENTION = ".md"
HTML_FILE_EXTENTION = ".html"
MARKDOWN_INDEX_FILE = f"__index__{MARKDOWN_FILE_EXTENTION}"
TEMPLATE_FILE_NAME = f"__template__{HTML_FILE_EXTENTION}"
HIDE_PREFIX = "#"


class InvalidDirectoryTree(Exception):
    pass


@dataclasses.dataclass(frozen=True)
class NavigationItem:
    source_file_path: str
    sub_items: t.List[NavigationItem]
    template: str
    is_hidden: bool

    @staticmethod
    def remove_modifiers(filename) -> str:
        parts = filename.split("_")
        try:
            int(parts[0])
        except ValueError:
            pass
        else:
            parts = parts[1:]
        if parts[0] == HIDE_PREFIX:
            parts = parts[1:]
        return "_".join(parts)

    def html_file_name(self):
        return (
            self.remove_modifiers(
                os.path.basename(self.source_file_path)[: -len(MARKDOWN_FILE_EXTENTION)]
            )
            + HTML_FILE_EXTENTION
        )

    def html_file_path(self):
        return os.path.join(
            self.relative_file_directory(),
            self.html_file_name(),
        )

    def relative_file_directory(self):
        return os.path.dirname(self.source_file_path)

    @classmethod
    def humanize(cls, filename: str):
        return " ".join(cls.remove_modifiers(filename).split("_")).title()

    def title(self):
        if self.is_navigation_parent():
            return self.humanize(self.directory_name())
        return self.humanize(
            os.path.basename(self.source_file_path)[: -len(MARKDOWN_FILE_EXTENTION)]
        )

    def directory_name(self):
        return os.path.basename(self.relative_file_directory())

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
        for file_object in sorted(os.listdir(path)):
            full_path = os.path.join(path, file_object)
            file_object_path = os.path.relpath(full_path, root_dir)
            is_hidden = file_object.split("_")[0] == HIDE_PREFIX
            if cls.path_is_navigation_leaf(full_path):
                node = cls(file_object_path, [], template, is_hidden)
            elif cls.path_is_navigation_dir(full_path):
                node = cls(
                    os.path.join(file_object_path, MARKDOWN_INDEX_FILE),
                    cls.from_path(full_path, template=template, root_dir=root_dir),
                    template,
                    is_hidden,
                )
            else:
                continue
            items.append(node)

        return items

    def is_navigation_parent(self):
        return os.path.basename(self.source_file_path) == MARKDOWN_INDEX_FILE

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


@dataclasses.dataclass(frozen=True)
class PageBuilder:
    source_dir: str
    destination_dir: str
    gh_token: str
    static_files: t.Tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "jinja_env",
            jinja2.Environment(loader=jinja2.FileSystemLoader(self.source_dir)),
        )
        object.__setattr__(
            self, "navigation", NavigationItem.from_path(self.source_dir)
        )

    @functools.lru_cache
    def build_markdown(self, file_path: str) -> str:
        with open(os.path.join(self.source_dir, file_path)) as file_:
            text = file_.read()
        response = requests.post(
            "https://api.github.com/markdown",
            json={"text": text},
            headers={"Accept": "application/vnd.github.v3+json"},
            auth=auth.HTTPBasicAuth("mmEissen", self.gh_token),
        )
        response.raise_for_status()
        return str(response.content, "utf-8")

    def build_page(
        self,
        navigation_item: NavigationItem,
        context: t.Dict[str, t.Any],
    ) -> str:
        title = navigation_item.title()
        navbar = self.build_navbar_for(navigation_item)
        content = self.build_markdown(navigation_item.source_file_path)
        children = [
            (
                child.title(),
                os.path.relpath(
                    child.html_file_path(), navigation_item.relative_file_directory()
                ),
                self.build_markdown(child.source_file_path),
            )
            for child in navigation_item.sub_items
        ]
        root_dir = os.path.relpath(
            self.source_dir,
            os.path.join(self.source_dir, navigation_item.relative_file_directory()),
        )
        return self.jinja_env.get_template(navigation_item.template).render(
            {
                **context,
                "content": content,
                "navbar": navbar,
                "title": title,
                "children": children,
                "root_dir": root_dir,
            }
        )

    def build_navbar_for(
        self, requester_item: NavigationItem, root_items: t.List[NavigationItem] = None
    ):
        if root_items is None:
            root_items = self.navigation
        if not root_items:
            return []
        navbar = [
            (
                item.title(),
                os.path.relpath(
                    item.html_file_path(), requester_item.relative_file_directory()
                ),
                self.build_navbar_for(requester_item, item.sub_items),
            )
            for item in root_items
            if not item.is_hidden
        ]
        return navbar

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
            print(html_file_path)
            os.makedirs(os.path.dirname(html_file_path), exist_ok=True)
            with open(html_file_path, "w") as file_:
                file_.write(page)
            if item.is_navigation_parent():
                self.build_pages_recursive(
                    item.sub_items,
                    global_context,
                )

    def copy_static_files(self):
        for name in self.static_files:
            full_source_name = os.path.join(self.source_dir, name)
            full_destination_name = os.path.join(self.destination_dir, name)
            if os.path.isdir(full_source_name):
                shutil.copytree(full_source_name, full_destination_name, dirs_exist_ok=True)
            elif os.path.isfile(full_source_name):
                shutil.copy2(full_source_name, full_destination_name)
    
    def clean(self):
        if os.path.isdir(self.destination_dir):
            shutil.rmtree(self.destination_dir)

    def build(self, clean=False):
        if clean:
            self.clean()
        self.build_pages_recursive()
        self.copy_static_files()


@click.command()
@click.argument("source", type=click.Path())
@click.argument("destination")
@click.option("--gh-token", type=str, envvar="GH_TOKEN")
@click.option("--keep", type=click.Path(), multiple=True)
@click.option("--clean", is_flag=True)
def build(source: str, destination: str, gh_token: str, keep: t.List[str], clean: bool):
    PageBuilder(source, destination, gh_token, tuple(keep)).build(clean)


if __name__ == "__main__":
    build()
