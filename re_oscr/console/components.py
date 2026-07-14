"""Reusable, style-free Command Console widget builders.

Builders assign semantic object names and dynamic properties.  Themeable values come from the
single application stylesheet generated in :mod:`re_oscr.console.tokens`.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from .tokens import px


def _role(widget: QWidget, role: str, accent_index: int | None = None) -> QWidget:
    widget.setProperty("consoleRole", role)
    if accent_index is not None:
        widget.setProperty("accentIndex", str(accent_index))
    return widget


def primary_navigation_button(
        scale: float, index: int, label: str, accent_index: int,
        object_name: str, mirrored: bool = False) -> QPushButton:
    button = QPushButton(f"{index:02d}   {label.upper()}")
    button.setObjectName(object_name)
    _role(button, "primaryNav", accent_index)
    button.setProperty("mirrored", mirrored)
    button.setProperty("visualActive", False)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(px(50, scale))
    return button


def mode_button(
        scale: float, code: str, label: str, accent_index: int,
        object_name: str) -> QPushButton:
    button = QPushButton(f"{code}  {label.upper()}")
    button.setObjectName(object_name)
    _role(button, "modeControl", accent_index)
    button.setCheckable(True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(px(30, scale))
    return button


def action_button(
        label: str, object_name: str, accent_index: int | None = None,
        primary: bool = False) -> QPushButton:
    button = QPushButton(label)
    button.setObjectName(object_name)
    _role(button, "actionButton", accent_index)
    button.setProperty("primary", primary)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def chip(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    _role(label, "chip")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


@dataclass
class Panel:
    frame: QFrame
    body: QFrame
    body_layout: QVBoxLayout
    eyebrow: QLabel | None = None
    title: QLabel | None = None
    cap: QFrame | None = None


def capped_panel(
        scale: float, object_name: str, eyebrow: str, title: str,
        accent_index: int) -> Panel:
    frame = QFrame()
    frame.setObjectName(object_name)
    _role(frame, "cappedPanel")
    root = QVBoxLayout()
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    cap = QFrame()
    cap.setObjectName(f"{object_name}Cap")
    _role(cap, "panelCap", accent_index)
    cap_layout = QVBoxLayout()
    cap_layout.setContentsMargins(px(12, scale), px(7, scale), px(12, scale), px(7, scale))
    cap_layout.setSpacing(px(2, scale))
    eyebrow_label = QLabel(eyebrow)
    _role(eyebrow_label, "eyebrow")
    title_label = QLabel(title)
    _role(title_label, "heading")
    cap_layout.addWidget(eyebrow_label)
    cap_layout.addWidget(title_label)
    cap.setLayout(cap_layout)
    root.addWidget(cap)

    body = QFrame()
    body.setObjectName(f"{object_name}Body")
    body_layout = QVBoxLayout()
    body_layout.setContentsMargins(px(12, scale), px(10, scale), px(12, scale), px(10, scale))
    body_layout.setSpacing(px(8, scale))
    body.setLayout(body_layout)
    root.addWidget(body, 1)
    frame.setLayout(root)
    return Panel(frame, body, body_layout, eyebrow_label, title_label, cap)


def embedded_surface(scale: float, object_name: str) -> Panel:
    frame = QFrame()
    frame.setObjectName(object_name)
    _role(frame, "embeddedSurface")
    body_layout = QVBoxLayout()
    body_layout.setContentsMargins(px(8, scale), px(8, scale), px(8, scale), px(8, scale))
    body_layout.setSpacing(px(6, scale))
    frame.setLayout(body_layout)
    return Panel(frame, frame, body_layout)


def cap_line(
        scale: float, object_name: str, eyebrow: str, title: str,
        accent_index: int) -> Panel:
    frame = QFrame()
    frame.setObjectName(object_name)
    _role(frame, "capLine", accent_index)
    layout = QHBoxLayout()
    layout.setContentsMargins(px(10, scale), px(6, scale), px(10, scale), px(6, scale))
    layout.setSpacing(px(10, scale))
    identity = QVBoxLayout()
    identity.setContentsMargins(0, 0, 0, 0)
    identity.setSpacing(0)
    eyebrow_label = QLabel(eyebrow)
    _role(eyebrow_label, "eyebrow")
    title_label = QLabel(title)
    _role(title_label, "heading")
    identity.addWidget(eyebrow_label)
    identity.addWidget(title_label)
    layout.addLayout(identity, 1)
    frame.setLayout(layout)
    return Panel(frame, frame, layout, eyebrow_label, title_label, frame)


def list_row(object_name: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName(object_name)
    _role(frame, "listRow")
    return frame
