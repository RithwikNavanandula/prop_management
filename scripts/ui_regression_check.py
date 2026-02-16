"""UI regression checks for layering/layout invariants.

Run:
    python scripts/ui_regression_check.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "app" / "static" / "css" / "style.css"
PROPERTIES_TEMPLATE_PATH = ROOT / "app" / "templates" / "properties" / "index.html"
BASE_TEMPLATE_PATH = ROOT / "app" / "templates" / "base.html"


def _extract_selector_block(css_text: str, selector: str) -> list[str]:
    pattern = re.compile(rf"{re.escape(selector)}\s*\{{(.*?)\}}", re.S)
    return [match.group(1) for match in pattern.finditer(css_text)]


def _selector_zindex(css_text: str, selector: str) -> int | None:
    blocks = _extract_selector_block(css_text, selector)
    z_values: list[int] = []
    for block in blocks:
        for m in re.finditer(r"z-index\s*:\s*(-?\d+)", block):
            z_values.append(int(m.group(1)))
    if not z_values:
        return None
    return z_values[-1]


def _check_css_layering(css_text: str) -> list[str]:
    errors: list[str] = []

    selectors = {
        ".topbar": _selector_zindex(css_text, ".topbar"),
        ".sidebar-overlay": _selector_zindex(css_text, ".sidebar-overlay"),
        ".sidebar": _selector_zindex(css_text, ".sidebar"),
        ".modal-backdrop": _selector_zindex(css_text, ".modal-backdrop"),
        ".modal": _selector_zindex(css_text, ".modal"),
        ".toast-container": _selector_zindex(css_text, ".toast-container"),
    }
    missing = [name for name, value in selectors.items() if value is None]
    if missing:
        errors.append(f"Missing z-index for selectors: {', '.join(missing)}")
        return errors

    if selectors[".sidebar"] <= selectors[".sidebar-overlay"]:
        errors.append("Expected `.sidebar` to be above `.sidebar-overlay`.")
    if selectors[".sidebar-overlay"] <= selectors[".topbar"]:
        errors.append("Expected `.sidebar-overlay` to be above `.topbar`.")
    if selectors[".modal-backdrop"] <= selectors[".sidebar"]:
        errors.append("Expected `.modal-backdrop` to be above `.sidebar`.")
    if selectors[".modal"] <= selectors[".modal-backdrop"]:
        errors.append("Expected `.modal` to be above `.modal-backdrop`.")
    if selectors[".toast-container"] <= selectors[".modal"]:
        errors.append("Expected `.toast-container` to be above `.modal`.")

    return errors


def _check_templates(properties_html: str, base_html: str) -> list[str]:
    errors: list[str] = []

    map_marker = 'id="propertiesMap"'
    modal_marker = 'id="addModal"'
    if map_marker not in properties_html:
        errors.append("Properties template is missing `#propertiesMap` container.")
    if modal_marker not in properties_html:
        errors.append("Properties template is missing `#addModal` modal.")
    if map_marker in properties_html and modal_marker in properties_html:
        if properties_html.find(map_marker) > properties_html.find(modal_marker):
            errors.append("`#propertiesMap` should appear before modal markup in properties template.")

    for required in ("function getMapTarget", "function renderPropertiesMap", "exportCurrentScreen"):
        if required == "exportCurrentScreen":
            if required not in base_html:
                errors.append("Base template missing `exportCurrentScreen()` function.")
        else:
            if required not in properties_html:
                errors.append(f"Properties template missing `{required}`.")

    return errors


def main() -> int:
    css_text = CSS_PATH.read_text(encoding="utf-8")
    properties_html = PROPERTIES_TEMPLATE_PATH.read_text(encoding="utf-8")
    base_html = BASE_TEMPLATE_PATH.read_text(encoding="utf-8")

    errors: list[str] = []
    errors.extend(_check_css_layering(css_text))
    errors.extend(_check_templates(properties_html, base_html))

    if errors:
        print("UI regression check: FAILED")
        for err in errors:
            print(f"- {err}")
        return 1

    print("UI regression check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
