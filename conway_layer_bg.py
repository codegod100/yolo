#!/usr/bin/env python3
"""Conway's Game of Life background using GTK4 layer-shell."""

from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import GLib, Gdk, Gtk, Gtk4LayerShell  # noqa: E402
import cairo  # noqa: E402


@dataclass
class LifeGrid:
    cols: int
    rows: int
    density: float = 0.18

    def __post_init__(self) -> None:
        self.cells: list[list[bool]] = [
            [random.random() < self.density for _ in range(self.cols)] for _ in range(self.rows)
        ]

    def step(self) -> None:
        next_cells = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        for y in range(self.rows):
            for x in range(self.cols):
                neighbors = 0
                for yy in (-1, 0, 1):
                    for xx in (-1, 0, 1):
                        if xx == 0 and yy == 0:
                            continue
                        ny = (y + yy) % self.rows
                        nx = (x + xx) % self.cols
                        neighbors += 1 if self.cells[ny][nx] else 0

                alive = self.cells[y][x]
                next_cells[y][x] = neighbors == 3 or (alive and neighbors == 2)
        self.cells = next_cells


class ConwaySurface:
    def __init__(self, app: Gtk.Application, monitor: Gdk.Monitor | None, index: int) -> None:
        self.cell_size = 10
        self.width = 0
        self.height = 0
        self.grid: LifeGrid | None = None
        self.generation = 0

        self.window = Gtk.ApplicationWindow(application=app)
        self.window.set_decorated(False)
        self.window.set_resizable(True)
        self.window.set_title(f"yolo-conway-bg-{index}")

        Gtk4LayerShell.init_for_window(self.window)
        Gtk4LayerShell.set_layer(self.window, Gtk4LayerShell.Layer.BACKGROUND)
        Gtk4LayerShell.set_keyboard_mode(self.window, Gtk4LayerShell.KeyboardMode.NONE)
        Gtk4LayerShell.set_namespace(self.window, f"yolo-greeter-bg-{index}")
        Gtk4LayerShell.set_exclusive_zone(self.window, 0)
        self.monitor: Gdk.Monitor | None = None
        self.set_monitor(monitor)
        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT,
        ):
            Gtk4LayerShell.set_anchor(self.window, edge, True)

        if hasattr(self.window, "set_can_target"):
            self.window.set_can_target(False)

        # Request full output size to avoid tiny default allocations.
        if monitor is None:
            self.window.set_default_size(1920, 1080)

        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.area.set_draw_func(self.on_draw)
        if hasattr(self.area, "set_can_target"):
            self.area.set_can_target(False)
        self.window.set_child(self.area)
        self.window.present()

        GLib.timeout_add(120, self.on_tick)

    def ensure_grid(self, width: int, height: int) -> None:
        cols = max(8, math.ceil(width / self.cell_size))
        rows = max(8, math.ceil(height / self.cell_size))
        if self.grid and self.grid.cols == cols and self.grid.rows == rows:
            return
        self.grid = LifeGrid(cols=cols, rows=rows)
        self.generation = 0

    def on_tick(self) -> bool:
        width = max(1, self.area.get_width())
        height = max(1, self.area.get_height())
        if width != self.width or height != self.height:
            self.width = width
            self.height = height
            self.ensure_grid(width, height)

        if self.grid is not None:
            self.grid.step()
            self.generation += 1
            if self.generation % 700 == 0:
                self.grid = LifeGrid(cols=self.grid.cols, rows=self.grid.rows, density=0.15)

        self.area.queue_draw()
        return True

    def on_draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int) -> None:
        self.ensure_grid(width, height)
        grid = self.grid
        if grid is None:
            return

        cr.set_source_rgb(0.02, 0.03, 0.05)
        cr.paint()

        # Dim grid dots
        cr.set_source_rgba(0.16, 0.18, 0.22, 0.25)
        for y in range(grid.rows):
            for x in range(grid.cols):
                px = x * self.cell_size
                py = y * self.cell_size
                cr.rectangle(px, py, 1, 1)
        cr.fill()

        # Live cells
        cr.set_source_rgba(0.51, 0.80, 1.0, 0.52)
        pad = 1
        size = max(1, self.cell_size - 2 * pad)
        for y in range(grid.rows):
            row = grid.cells[y]
            for x in range(grid.cols):
                if not row[x]:
                    continue
                px = x * self.cell_size + pad
                py = y * self.cell_size + pad
                cr.rectangle(px, py, size, size)
        cr.fill()

    def set_monitor(self, monitor: Gdk.Monitor | None) -> None:
        self.monitor = monitor
        if monitor is None:
            return
        Gtk4LayerShell.set_monitor(self.window, monitor)
        geo = monitor.get_geometry()
        self.window.set_default_size(geo.width, geo.height)


class ConwayBackground:
    def __init__(self, app: Gtk.Application) -> None:
        self.app = app
        self.surfaces: list[ConwaySurface] = []
        self.display = Gdk.Display.get_default()
        self.reconcile_surfaces()
        GLib.timeout_add(1200, self.on_reconcile_tick)

    def on_reconcile_tick(self) -> bool:
        self.reconcile_surfaces()
        return True

    def reconcile_surfaces(self) -> None:
        if self.display is None:
            if not self.surfaces:
                self.surfaces.append(ConwaySurface(self.app, None, 0))
            return

        monitors = self.display.get_monitors()
        count = monitors.get_n_items()
        if count == 0:
            if not self.surfaces:
                self.surfaces.append(ConwaySurface(self.app, None, 0))
            return

        while len(self.surfaces) < count:
            idx = len(self.surfaces)
            monitor = monitors.get_item(idx)
            self.surfaces.append(ConwaySurface(self.app, monitor, idx))

        while len(self.surfaces) > count:
            surface = self.surfaces.pop()
            surface.window.close()

        for idx, surface in enumerate(self.surfaces):
            monitor = monitors.get_item(idx)
            if monitor is not None and monitor is not surface.monitor:
                surface.set_monitor(monitor)


def wait_for_wayland_ready(timeout_s: float = 6.0) -> bool:
    """Wait until a Wayland socket and GTK display are available."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        xdg_runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "")
        wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
        socket_ok = False
        if xdg_runtime_dir and wayland_display:
            socket_ok = os.path.exists(os.path.join(xdg_runtime_dir, wayland_display))

        if socket_ok and Gtk.init_check():
            return True
        time.sleep(0.1)
    return False


def main() -> int:
    if not wait_for_wayland_ready():
        print("yolo-conway-bg: Wayland/GTK not ready; exiting.")
        return 1

    app = Gtk.Application(application_id="wtf.yolo.greeter.conwaybg")

    def on_activate(_app: Gtk.Application) -> None:
        # Keep a strong reference for the lifetime of the application.
        _app.bg = ConwayBackground(_app)  # type: ignore[attr-defined]

    app.connect("activate", on_activate)
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
