"""Makes printable QR and ArUco cards for the QR placement trial (CLAUDE.md §3).

A short worker ID such as SS-0001 fits the smallest QR symbol (21 x 21 modules) even at the highest
error correction level H, which keeps each module as large as possible for a given card size.
ArUco markers (4x4 dictionary, 6 x 6 cells with their border) are the fallback if QR does not read
from 3 m: fewer, larger cells. Each card gets its own page. The size is the width of the black
symbol; the white margin around it is extra and must be kept when cutting the card out.

Print the PDF at 100% (actual size), not "fit to page"; the 10 cm line on each page checks this.

Usage:
    python scripts/make_qr_cards.py --ids SS-0001 --sizes 5 7 10 15 --out data/qr/cards.pdf
"""

import argparse
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ARUCO_DICT = cv2.aruco.DICT_4X4_50  # ids 0..49
PAPER_CM = {"A4": (21.0, 29.7), "A3": (29.7, 42.0)}
MARGIN_CM = 1.0  # most printers cannot print closer to the edge
# White border in cells, on top of the paper margin. ArUco cells are big, so half a cell is plenty.
QUIET_CELLS = {"qr": 2, "aruco": 0.5}


def qr_matrix(text: str) -> np.ndarray:
    """QR symbol at one pixel per module, without the quiet zone (0 = black, 255 = white)."""
    params = cv2.QRCodeEncoder_Params()
    params.correction_level = cv2.QRCODE_ENCODER_CORRECT_LEVEL_H
    img = cv2.QRCodeEncoder.create(params).encode(text)
    ys, xs = np.where(img == 0)  # the finder patterns reach all four edges of the symbol
    return img[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def aruco_id(worker_id: str) -> int:
    """SS-0007 -> 7: the marker id is the number in the worker id."""
    digits = re.sub(r"\D", "", worker_id)
    if not digits or int(digits) >= 50:
        raise ValueError(f"{worker_id}: ArUco 4x4_50 needs a number between 0 and 49 in the id")
    return int(digits)


def aruco_matrix(marker_id: int) -> np.ndarray:
    """ArUco marker at one pixel per cell, border included (6 x 6)."""
    return cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(ARUCO_DICT), marker_id, 6)


def render(matrix: np.ndarray, size_cm: float, dpi: int, quiet_cells: float) -> np.ndarray:
    """Scales the symbol to size_cm wide with whole pixels per cell and adds the white margin."""
    cell = max(1, round(size_cm / 2.54 * dpi / matrix.shape[1]))
    img = cv2.resize(matrix, None, fx=cell, fy=cell, interpolation=cv2.INTER_NEAREST)
    q = round(quiet_cells * cell)
    return cv2.copyMakeBorder(img, q, q, q, q, cv2.BORDER_CONSTANT, value=255)


def card_page(card: np.ndarray, label: str, paper: str, dpi: int) -> Image.Image:
    w_cm, h_cm = PAPER_CM[paper]
    px = lambda cm: round(cm / 2.54 * dpi)
    page = Image.new("L", (px(w_cm), px(h_cm)), 255)
    left = (page.width - card.shape[1]) // 2
    page.paste(Image.fromarray(card), (left, px(MARGIN_CM)))

    draw = ImageDraw.Draw(page)
    # thin grey cut line around the white margin
    top = px(MARGIN_CM)
    draw.rectangle([left - 2, top - 2, left + card.shape[1] + 1, top + card.shape[0] + 1], outline=170, width=2)
    font = ImageFont.load_default(size=px(0.6))
    y = top + card.shape[0] + px(0.8)
    draw.text((px(MARGIN_CM), y), label, fill=0, font=font)
    y += px(1.2)
    draw.line([(px(MARGIN_CM), y), (px(MARGIN_CM) + px(10), y)], fill=0, width=4)
    draw.text((px(MARGIN_CM), y + px(0.3)), "10 cm - measure this line to check the print scale", fill=0, font=font)
    return page


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", nargs="+", default=["SS-0001"], help="worker ids (QR text; the number is the ArUco id)")
    parser.add_argument("--sizes", nargs="+", type=float, default=[5, 7, 10, 15], help="symbol widths in cm")
    parser.add_argument("--markers", nargs="+", choices=["qr", "aruco"], default=["qr", "aruco"])
    parser.add_argument("--paper", choices=sorted(PAPER_CM), default="A4")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--out", type=Path, default=Path("data/qr/cards.pdf"))
    args = parser.parse_args()

    printable_cm = PAPER_CM[args.paper][0] - 2 * MARGIN_CM
    pages = []
    for worker in args.ids:
        for marker in args.markers:
            matrix = qr_matrix(worker) if marker == "qr" else aruco_matrix(aruco_id(worker))
            for size in args.sizes:
                card = render(matrix, size, args.dpi, QUIET_CELLS[marker])
                width_cm = card.shape[1] / args.dpi * 2.54
                if width_cm > printable_cm:
                    parser.error(f"{size} cm {marker} is {width_cm:.1f} cm with its margin; use a bigger --paper")
                label = f"{worker}  |  {marker.upper()}  |  {size:g} cm"
                pages.append(card_page(card, label, args.paper, args.dpi))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(args.out, save_all=True, append_images=pages[1:], resolution=args.dpi)
    print(f"{len(pages)} pages -> {args.out}  (print at 100%, check the 10 cm line)")


if __name__ == "__main__":
    main()
