import argparse
from pathlib import Path

import easyocr
import pypdfium2 as pdfium
from PIL import Image
from pdfminer.high_level import extract_text


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def extract_pdf_text(pdf_path: Path, page_index: int) -> str:
    try:
        text = extract_text(str(pdf_path), page_numbers=[page_index], maxpages=1)
        return (text or "").strip()
    except Exception:
        return ""


def render_page(pdf: pdfium.PdfDocument, page_index: int, scale: float, out_path: Path) -> Path:
    page = pdf[page_index]
    image = page.render(scale=scale).to_pil()
    image.save(out_path)
    return out_path


def run_ocr(reader: easyocr.Reader, image_path: Path) -> str:
    items = reader.readtext(str(image_path), detail=0, paragraph=True)
    return "\n".join(line.strip() for line in items if line.strip())


def crop_tiles(image_path: Path, tiles_dir: Path, rows: int, cols: int, overlap: float) -> list[Path]:
    ensure_dir(tiles_dir)
    image = Image.open(image_path)
    width, height = image.size
    tile_w = width / cols
    tile_h = height / rows
    overlap_x = int(tile_w * overlap)
    overlap_y = int(tile_h * overlap)
    out_paths: list[Path] = []

    for row in range(rows):
        for col in range(cols):
            left = max(0, int(col * tile_w) - overlap_x)
            top = max(0, int(row * tile_h) - overlap_y)
            right = min(width, int((col + 1) * tile_w) + overlap_x)
            bottom = min(height, int((row + 1) * tile_h) + overlap_y)
            tile_path = tiles_dir / f"r{row + 1:02d}_c{col + 1:02d}.png"
            image.crop((left, top, right, bottom)).save(tile_path)
            out_paths.append(tile_path)

    return out_paths


def dedupe_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        key = " ".join(line.split())
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def run_tiled_ocr(
    reader: easyocr.Reader,
    image_path: Path,
    page_tiles_dir: Path,
    rows: int,
    cols: int,
    overlap: float,
) -> str:
    tile_paths = crop_tiles(image_path, page_tiles_dir, rows, cols, overlap)
    all_lines: list[str] = []
    for tile_path in tile_paths:
        items = reader.readtext(str(tile_path), detail=0, paragraph=True)
        all_lines.extend(line.strip() for line in items if line.strip())
    return "\n".join(dedupe_lines(all_lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract text from drawing PDFs.")
    parser.add_argument("pdf", type=Path, help="Path to the source PDF.")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("output/pdf_extract"),
        help="Directory for rendered images and text outputs.",
    )
    parser.add_argument("--scale", type=float, default=4.0, help="PDF render scale.")
    parser.add_argument("--tile-rows", type=int, default=3, help="OCR tile row count.")
    parser.add_argument("--tile-cols", type=int, default=3, help="OCR tile column count.")
    parser.add_argument("--tile-overlap", type=float, default=0.12, help="Tile overlap ratio.")
    parser.add_argument(
        "--langs",
        nargs="+",
        default=["ch_sim", "en"],
        help="EasyOCR language list.",
    )
    parser.add_argument(
        "--pages",
        nargs="*",
        type=int,
        help="1-based page numbers to process. Default: all pages.",
    )
    args = parser.parse_args()

    pdf_path = args.pdf.resolve()
    outdir = args.outdir.resolve()
    images_dir = outdir / "images"
    tiles_dir = outdir / "tiles"
    text_dir = outdir / "text"
    ensure_dir(images_dir)
    ensure_dir(tiles_dir)
    ensure_dir(text_dir)

    reader = easyocr.Reader(args.langs, gpu=False)
    pdf = pdfium.PdfDocument(str(pdf_path))

    if args.pages:
        page_indices = [page_no - 1 for page_no in args.pages if 1 <= page_no <= len(pdf)]
    else:
        page_indices = list(range(len(pdf)))

    summary_lines = [
        f"pdf={pdf_path}",
        f"pages={len(pdf)}",
        f"selected_pages={','.join(str(i + 1) for i in page_indices)}",
        f"scale={args.scale}",
    ]

    for page_index in page_indices:
        page_no = page_index + 1
        image_path = images_dir / f"page_{page_no:02d}.png"
        txt_path = text_dir / f"page_{page_no:02d}.txt"

        raw_text = extract_pdf_text(pdf_path, page_index)
        render_page(pdf, page_index, args.scale, image_path)
        ocr_text = run_tiled_ocr(
            reader,
            image_path,
            tiles_dir / f"page_{page_no:02d}",
            args.tile_rows,
            args.tile_cols,
            args.tile_overlap,
        )

        merged = []
        if raw_text:
            merged.append("[pdf_text]")
            merged.append(raw_text)
        if ocr_text:
            merged.append("[ocr_text]")
            merged.append(ocr_text)
        txt_path.write_text("\n".join(merged).strip() + "\n", encoding="utf-8")

        summary_lines.append(
            f"page={page_no} pdf_text_len={len(raw_text)} ocr_text_len={len(ocr_text)} image={image_path.name}"
        )

    (outdir / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
