"""JSON forms of notifiables and notifications for Django Tasks, which only accepts JSON."""

import dataclasses
import importlib
import math
from collections.abc import Mapping
from typing import Any, Final, cast

from django.apps import apps
from django.db import models
from goatnotify.core._json import JsonValue
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable, Notification

MODEL_TAG: Final = "model"
JSON_TAG: Final = "json"
JSON_SCALARS: Final = (str, int, float, bool, type(None))


def dump_model(instance: models.Model) -> dict[str, JsonValue]:
    if instance.pk is None:
        raise ConfigurationError(f"{type(instance).__qualname__} must be saved before it is queued")
    pk: object = instance.pk
    json_pk: JsonValue = pk if isinstance(pk, str | int) and type(pk) is not bool else str(pk)
    return {"label": instance._meta.label_lower, "pk": json_pk}


def load_model(reference: Mapping[str, JsonValue]) -> models.Model:
    label = reference.get("label")
    if not isinstance(label, str):
        raise ConfigurationError("Malformed queued model reference")
    return apps.get_model(label)._default_manager.get(pk=reference.get("pk"))


def load_notifiable(reference: Mapping[str, JsonValue]) -> Notifiable:
    instance = load_model(reference)
    if not callable(getattr(instance, "route_notification", None)):
        raise ConfigurationError(f"{type(instance).__qualname__} is not notifiable")
    return cast("Notifiable", instance)


def dump_notification(notification: Notification[Any]) -> dict[str, JsonValue]:
    cls = type(notification)
    if not dataclasses.is_dataclass(notification) or "<locals>" in cls.__qualname__:
        raise ConfigurationError(
            f"{cls.__qualname__} must be a module-level dataclass to be queued with Django Tasks"
        )
    fields: dict[str, JsonValue] = {}
    for field in dataclasses.fields(notification):
        if not field.init:
            continue
        value: object = getattr(notification, field.name)
        if isinstance(value, models.Model):
            fields[field.name] = {MODEL_TAG: dump_model(value)}
        elif _round_trips(value):
            fields[field.name] = {JSON_TAG: cast("JsonValue", value)}
        else:
            raise ConfigurationError(
                f"{cls.__qualname__}.{field.name} must be plain JSON (str, int, float, bool, "
                "None, list, dict with str keys) or a saved model instance"
            )
    return {"class": f"{cls.__module__}:{cls.__qualname__}", "fields": fields}


def load_notification(payload: Mapping[str, JsonValue]) -> Notification[Any]:
    path, fields = payload.get("class"), payload.get("fields")
    if not isinstance(path, str) or not isinstance(fields, dict):
        raise ConfigurationError("Malformed queued notification")
    module_name, _, qualname = path.partition(":")
    # Task payloads may sit in a database table, so only installed apps' modules are importable.
    if not _in_installed_app(module_name):
        raise ConfigurationError(f"{module_name!r} is not part of an installed app")
    target: object = importlib.import_module(module_name)  # nosemgrep
    for part in qualname.split("."):
        target = getattr(target, part)
    if not (isinstance(target, type) and issubclass(target, Notification)):
        raise ConfigurationError(f"{path} is not a Notification")
    arguments = {name: _load_field(value) for name, value in fields.items()}
    return cast("type[Notification[Any]]", target)(**arguments)


def _round_trips(value: object) -> bool:
    # Exact types: tuples, enums and other subclasses would come back as plain JSON values.
    if type(value) is float:
        return math.isfinite(value)
    if type(value) in JSON_SCALARS:
        return True
    if type(value) is list:
        return all(_round_trips(item) for item in cast("list[object]", value))
    if type(value) is dict:
        items = cast("dict[object, object]", value).items()
        return all(type(key) is str and _round_trips(item) for key, item in items)
    return False


def _load_field(encoded: JsonValue) -> object:
    if not isinstance(encoded, dict) or len(encoded) != 1:
        raise ConfigurationError("Malformed queued notification field")
    ((tag, value),) = encoded.items()
    if tag == JSON_TAG:
        return value
    if tag == MODEL_TAG and isinstance(value, dict):
        return load_model(value)
    raise ConfigurationError("Malformed queued notification field")


def _in_installed_app(module_name: str) -> bool:
    return any(
        module_name == config.name or module_name.startswith(f"{config.name}.")
        for config in apps.get_app_configs()
    )
