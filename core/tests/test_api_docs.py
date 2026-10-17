from django.conf import settings
from drf_spectacular.generators import SchemaGenerator

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _schema():
    return SchemaGenerator().get_schema(request=None, public=True)


def test_every_endpoint_belongs_to_a_listed_docs_group() -> None:
    groups = {tag["name"] for tag in settings.SPECTACULAR_SETTINGS["TAGS"]}
    ungrouped = [
        f"{method.upper()} {path} -> {operation.get('tags')}"
        for path, operations in _schema()["paths"].items()
        for method, operation in operations.items()
        if method in HTTP_METHODS and (
            len(operation.get("tags", [])) != 1 or operation["tags"][0] not in groups
        )
    ]

    assert ungrouped == []


def test_every_docs_group_has_endpoints() -> None:
    used = {
        tag
        for operations in _schema()["paths"].values()
        for method, operation in operations.items()
        if method in HTTP_METHODS
        for tag in operation.get("tags", [])
    }
    listed = [tag["name"] for tag in settings.SPECTACULAR_SETTINGS["TAGS"]]

    assert [name for name in listed if name not in used] == []


def test_no_endpoint_is_mounted_twice() -> None:
    assert [path for path in _schema()["paths"] if path.startswith("/api/api/")] == []
