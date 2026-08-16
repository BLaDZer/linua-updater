# Task 35 — Fix CompletionDialog clipping on Linux (auto-size to fit content)

## Context

After a successful install, `CompletionDialog` (`linua_updater/ui/dialogs.py:21`) shows a success
message plus the wrapped warning "IMPORTANT: DLC need to be activated with DLC Unlocker!...". On
Windows (Segoe UI) the warning wraps to a height that fits inside the hard-coded
`setFixedSize(450, 200)` (`dialogs.py:25`); on Linux the default font renders taller/wider, the
warning wraps onto extra lines, and the fixed height clips the text and the Close button, so the
dialog looks small and cropped.

Root cause: a **fixed window height** combined with `QLabel.setWordWrap(True)` — when the font
metrics need more vertical space than allotted, Qt clips the overflow instead of growing the dialog.

## How it works now

- `dialogs.py:25` — `setFixedSize(450, 200)`.
- `dialogs.py:40-43` — word-wrapped warning label; `addStretch()` (line 46) only absorbs allotted
  space, it cannot create height that was never given to the layout.
- Vertical budget (margins 30×2 + spacing 15×3 + title ≈38 px + warning ≈34 px at 2 lines +
  button ≈42 px) ≈ 261 px > 200 px fixed → overflow clipped.

## How it should work

- The dialog always fully fits its content (warning text + Close button) on Linux, macOS and
  Windows, at any font/DPI.
- The wrap width is deterministic so the required height is stable; the dialog sizes itself to the
  layout's computed `sizeHint()` instead of a hard-coded height.
- UX unchanged: still modal, still user-fixed (non-resizable), same text/style/colors.

## What needs fixing

In `linua_updater/ui/dialogs.py`:

1. Import `QLayout` from `PyQt6.QtWidgets`.
2. In `CompletionDialog.__init__` replace `self.setFixedSize(450, 200)` with
   `self.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)` (keeps the dialog fixed but
   auto-resizes it to the layout's `sizeHint`), plus `self.setMinimumSize(450, 220)` as a safety
   floor.
3. In `setup_ui`, after creating the warning label, add `warning_text.setFixedWidth(390)`
   (450 − 30 px ×2 margins) so `QLabel` word-wrap triggers at a fixed width and the layout reports a
   correct wrapped height instead of the ambiguous one-line `sizeHint()` — this is what makes the
   computed height deterministic across platforms.
4. Keep the title, colors, margins, button styling and `addStretch()` unchanged.

## Not in scope

- Changing the message text/wording, styles or fonts.
- Retouching the other dialogs' fixed sizes.

## Tests

Headless, no `QApplication` (per AGENTS.md), in `tests/test_ui_defaults.py`:
- `test_completion_dialog_heights_auto_size` — via `inspect.getsource(CompletionDialog)` assert it no
  longer calls `setFixedSize(450, 200)`.
- `test_completion_dialog_uses_fixed_size_constraint` — source-assert it calls
  `setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)`.
- `test_completion_dialog_warning_wrap_width_fixed` — assert the warning label picks up a fixed wrap
  width (`setFixedWidth(390)`) or a `WARNING_WRAP_WIDTH` module constant is positive/finite.

## Docs

- `docs/architecture.md` — Dialogs table (line 95): note `CompletionDialog` auto-sizes to fit its
  wrapped warning text on all platforms.

## Verification

```bash
python -m pytest tests/ -v
./scripts/check.sh   # pytest + ruff
```

Manual smoke on Linux: install any single DLC; the completion dialog shows both warning lines and the
Close button in full, slightly taller than on Windows but never clipped.