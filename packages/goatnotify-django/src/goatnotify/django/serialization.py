"""JSON forms of notifiables and notifications for Django Tasks, which only accepts JSON."""

import dataclasses
import importlib
import json
from collections.abc import Mapping
from typing import Any, Final, cast

from django.apps import apps
from django.db import models
from goatnotify.core._json import JsonValue
from goatnotify.core.errors import ConfigurationError
from goatnotify.core.notification import Notifiable, Notification

MODEL_KEY: Final = "__model__"


def dump_model(instance: models.Model) -> dict[str, JsonValue]:
    if instance.pk is None:
        raise ConfigurationError(f"{type(instance).__qualname__} must be saved before it is queued")
    pk: object = instance.pk
    return {
        MODEL_KEY: instance._meta.label_lower,
        "pk": pk if isinstance(pk, str | int) else str(pk),
    }


def load_model(reference: Mapping[str, JsonValue]) -> models.Model:
    label = reference.get(MODEL_KEY)
    if not isinstance(label, str):
        raise ConfigurationError("Malformed queued model reference")
    return apps.get_model(label)._default_manager.get(pk=reference["pk"])


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
            fields[field.name] = dump_model(value)
            continue
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"{cls.__qualname__}.{field.name} is not JSON serializable"
            ) from error
        fields[field.name] = cast("JsonValue", value)
    return {"class": f"{cls.__module__}:{cls.__qualname__}", "fields": fields}


def load_notification(payload: Mapping[str, JsonValue]) -> Notification[Any]:
    path, fields = payload.get("class"), payload.get("fields")
    if not isinstance(path, str) or not isinstance(fields, dict):
        raise ConfigurationError("Malformed queued notification")
    module_name, _, qualname = path.partition(":")
    target: object = importlib.import_module(module_name)
    for part in qualname.split("."):
        target = getattr(target, part)
    if not (isinstance(target, type) and issubclass(target, Notification)):
        raise ConfigurationError(f"{path} is not a Notification")
    arguments = {
        name: load_model(value) if isinstance(value, dict) and MODEL_KEY in value else value
        for name, value in fields.items()
    }
    return cast("type[Notification[Any]]", target)(**arguments)
