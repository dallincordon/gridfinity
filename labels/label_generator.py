from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Optional, Sequence, Union


# ----------------------------
# Text normalization for labels
# ----------------------------

FRACTION_SLASH = "⁄"  # U+2044

_fraction_pattern = re.compile(r"(?<!\d)(\d+)\s*/\s*(\d+)(?!\d)")

def normalize_label_text(text: str) -> str:
    """
    Replace any occurrence of 'a/b' (with optional spaces) with 'a ⁄ b'
    using the Unicode fraction slash and spaces.

    Examples:
      "5/16"      -> "5 ⁄ 16"
      "5 / 16"    -> "5 ⁄ 16"
      'x 5/16"'   -> 'x 5 ⁄ 16"'   (quotes preserved; no special handling)
      "ID 5/16 OD 1/2" -> "ID 5 ⁄ 16 OD 1 ⁄ 2"
    """
    return _fraction_pattern.sub(rf"\1 {FRACTION_SLASH} \2", str(text))


# ----------------------------
# Helpers
# ----------------------------

def _safe_stem(s: str) -> str:
    """Make a filesystem-safe filename stem."""
    s = s.strip().replace("×", "x")
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s)  # collapse repeated underscores
    return s.strip("_") or "label"


def _norm_size_for_folder(size: str) -> str:
    """
    Folder-friendly size string.
    - "M3" -> "m3"
    - "#4-40" -> "4-40" (drops '#')
    """
    s = size.strip().lower().replace("#", "")
    s = re.sub(r"\s+", "", s)
    return s


def default_section_dir(base_out: Path, *, kind: str, size: str, lock: bool = False) -> Path:
    """
    Organize outputs by size + category, e.g.:
      out/m3_bolts/
      out/4-40_bolts/
      out/m5_lockwashers/
    """
    s = _norm_size_for_folder(size)
    if kind == "bolt":
        return base_out / f"{s}_bolts"
    if kind == "nut":
        return base_out / f"{s}_nuts"
    if kind == "washer":
        return base_out / (f"{s}_lockwashers" if lock else f"{s}_washers")
    return base_out / "misc"


def run_gflabel(
    base: str,
    label: str,
    *,
    output: Path,
    font_style: str = "bold",
    margin: str = "0",
    gflabel_exe: str = "gflabel",
) -> None:
    """
    Call gflabel to generate a single output file.

    IMPORTANT:
    - label must be the raw label spec string (NO shell quotes)
    - newline should be a real '\\n' in the Python string
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        gflabel_exe,
        base,
        label,
        "--font-style",
        font_style,
        "--margin",
        str(margin),
        "-o",
        str(output),
    ]
    subprocess.run(cmd, check=True)


# ----------------------------
# Low-level specs (rendered 1:1)
# ----------------------------

@dataclass(frozen=True)
class BoltSpec:
    size: str
    length: str                     # rendered as ×{length}
    head_style: str = "socket"       # e.g. socket|pan|round|countersunk
    drive: str = "hex"               # e.g. hex|phillips|torx
    tapping: bool = False            # adds "tapping" flag inside {cullbolt(...)}
    partial_thread: bool = False     # adds "partial" flag inside {cullbolt(...)}
    grade_or_material: Optional[str] = None  # e.g. "316" or "12.9"


@dataclass(frozen=True)
class NutSpec:
    size: str
    extra: str = ""                  # second row text


@dataclass(frozen=True)
class WasherSpec:
    size: str
    extra: str = ""                  # second row text
    lock: bool = False               # lockwasher vs washer


# ----------------------------
# High-level batch requests (your "shopping list")
# ----------------------------

@dataclass(frozen=True)
class Bolts:
    bolt_type: str                   # e.g. "socket_hex"
    size: str                        # "M3" or "#4-40"
    lengths: Sequence[str]           # ["8","10"] or ['5/16"', ...]
    tapping: bool = False
    partial_thread: bool = False
    grade_or_material: Optional[str] = None


@dataclass(frozen=True)
class Nuts:
    size: str
    extras: Sequence[str] = ("",)    # multiple nut variants


@dataclass(frozen=True)
class Washers:
    size: str
    extras: Sequence[str] = ("",)    # multiple washer variants (dims, notes, etc.)
    lock: bool = False


BatchItem = Union[Bolts, Nuts, Washers]


# ----------------------------
# Layout renderer (encodes YOUR gflabel layout strings)
# ----------------------------

class CullenectLayout:
    base = "cullenect"

    def bolt_label(self, b: BoltSpec) -> str:
        # Always include flipped (you said you'll never need unflipped).
        args: list[str] = ["flipped"]
        if b.tapping:
            args.append("tapping")
        if b.partial_thread:
            args.append("partial")

        args += [b.head_style, b.drive]
        icon = "{cullbolt(" + ",".join(args) + ")}"

        top = normalize_label_text(b.size)
        if b.grade_or_material:
            top = normalize_label_text(f"{top} {b.grade_or_material}")

        length_text = normalize_label_text(b.length)
        return f"{icon}{{1|1}}{top}\n×{length_text}"

    def nut_label(self, n: NutSpec) -> str:
        size = normalize_label_text(n.size)
        extra = normalize_label_text(n.extra)
        return f"{{<}}{{nut}}{{1|2}}{size}\n{extra}"

    def washer_label(self, w: WasherSpec) -> str:
        icon = "{lockwasher}" if w.lock else "{washer}"
        size = normalize_label_text(w.size)
        extra = normalize_label_text(w.extra)
        return f"{{<}}{icon}{{1|2}}{size}\n{extra}"

    def bolt_filename(self, b: BoltSpec, ext: str = ".step") -> str:
        # "#4-40" -> "4_40"
        size = b.size.lower().replace("#", "").replace("-", "_")

        # decimal -> 'p' for filename friendliness: 0.375 -> 0p375
        length = (
            str(b.length)
            .replace("/", "_")
            .replace('"', "")   # drop inch quotes in filenames
            .replace(".", "p")
        )

        stem = f"{size}x{length}_{b.head_style}_{b.drive}"
        if b.tapping:
            stem += "_tapping"
        if b.partial_thread:
            stem += "_partial"
        if b.grade_or_material:
            stem += f"_{str(b.grade_or_material).lower()}"

        return _safe_stem(stem) + ext

    def nut_filename(self, n: NutSpec, ext: str = ".step") -> str:
        stem = f"{n.size.lower().replace('#','')}_nut"
        if n.extra:
            stem += f"_{str(n.extra).lower()}"
        return _safe_stem(stem) + ext

    def washer_filename(self, w: WasherSpec, ext: str = ".step") -> str:
        stem = f"{w.size.lower().replace('#','')}_{'lockwasher' if w.lock else 'washer'}"
        if w.extra:
            stem += f"_{str(w.extra).lower()}"
        return _safe_stem(stem) + ext


# ----------------------------
# Bolt type registry (your "socket_hex" vocabulary)
# ----------------------------

BOLT_TYPES = {
    "socket_hex":    dict(head_style="socket", drive="hex"),
    "pan_phillips":  dict(head_style="pan", drive="phillips"),
    "pan_torx":      dict(head_style="pan", drive="torx"),
    "csk_hex":       dict(head_style="countersunk", drive="hex"),
    "csk_torx":      dict(head_style="countersunk", drive="torx"),
    "csk_phillips":  dict(head_style="countersunk", drive="phillips"),
}


# ----------------------------
# Batch generator
# ----------------------------

class FastenerBatchGenerator:
    def __init__(
        self,
        *,
        layout: Optional[CullenectLayout] = None,
        out_dir: Path = Path("labels_out"),
        ext: str = ".step",
        font_style: str = "bold",
        margin: str = "0",
        gflabel_exe: str = "gflabel",
        section_dir_fn=default_section_dir,
    ):
        self.layout = layout or CullenectLayout()
        self.out_dir = out_dir
        self.ext = ext
        self.font_style = font_style
        self.margin = margin
        self.gflabel_exe = gflabel_exe
        self.section_dir_fn = section_dir_fn

    def expand(self, items: Sequence[BatchItem]) -> Sequence[tuple[str, Path]]:
        jobs: list[tuple[str, Path]] = []

        for item in items:
            if isinstance(item, Bolts):
                if item.bolt_type not in BOLT_TYPES:
                    raise ValueError(f"Unknown bolt_type: {item.bolt_type!r}. Add it to BOLT_TYPES.")
                bt = BOLT_TYPES[item.bolt_type]

                for L in item.lengths:
                    spec = BoltSpec(
                        size=item.size,
                        length=str(L),
                        head_style=bt["head_style"],
                        drive=bt["drive"],
                        tapping=item.tapping,
                        partial_thread=item.partial_thread,
                        grade_or_material=item.grade_or_material,
                    )
                    label = self.layout.bolt_label(spec)
                    section = self.section_dir_fn(self.out_dir, kind="bolt", size=spec.size)
                    out = section / self.layout.bolt_filename(spec, ext=self.ext)
                    jobs.append((label, out))

            elif isinstance(item, Nuts):
                for extra in item.extras:
                    spec = NutSpec(size=item.size, extra=extra)
                    label = self.layout.nut_label(spec)
                    section = self.section_dir_fn(self.out_dir, kind="nut", size=spec.size)
                    out = section / self.layout.nut_filename(spec, ext=self.ext)
                    jobs.append((label, out))

            elif isinstance(item, Washers):
                for extra in item.extras:
                    spec = WasherSpec(size=item.size, extra=extra, lock=item.lock)
                    label = self.layout.washer_label(spec)
                    section = self.section_dir_fn(self.out_dir, kind="washer", size=spec.size, lock=spec.lock)
                    out = section / self.layout.washer_filename(spec, ext=self.ext)
                    jobs.append((label, out))

            else:
                raise TypeError(f"Unsupported item: {item!r}")

        return jobs

    def make(self, items: Sequence[BatchItem]) -> Sequence[Path]:
        outputs: list[Path] = []
        for label, out in self.expand(items):
            run_gflabel(
                self.layout.base,
                label,
                output=out,
                font_style=self.font_style,
                margin=self.margin,
                gflabel_exe=self.gflabel_exe,
            )
            outputs.append(out)
        return outputs


# ----------------------------
# Example usage
# ----------------------------

if __name__ == "__main__":
    gen = FastenerBatchGenerator(out_dir=Path("labels_out"))

    outputs = gen.make([
        Bolts("socket_hex", "M3", lengths=["8", "10", "12"]),
        Bolts("socket_hex", "M3", lengths=["16"], partial_thread=True),
        Bolts("socket_hex", "M3", lengths=["20"], partial_thread=True, tapping=True),

        Bolts("pan_phillips", "#4-40", lengths=['5/16"', '3/8"', '1/2"']),

        Nuts("M5", extras=["", "NYLON", "ACORN", "SPLIT"]),

        Washers("M5", extras=["", "id 5/16 od 1/2 t 1/16"]),
        Washers("M5", lock=True, extras=[""]),
    ])

    print("Generated:")
    for p in outputs:
        print(" -", p)
