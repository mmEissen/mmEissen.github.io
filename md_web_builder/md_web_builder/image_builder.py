import click
from PIL import Image, ImageFilter, ImageOps, ImageChops, ImageDraw
import numpy as np

import math
import os


SIZES = [
    (920, "lg"),
    (460, "md"),
]


def rgb_to_cmyk(r, g, b):
    r = r / 255
    g = g / 255
    b = b / 255
    k = 1 - max(r, g, b)
    c = 1 if k == 1 else (1 - r - k) / (1 - k)
    m = 1 if k == 1 else (1 - g - k) / (1 - k)
    y = 1 if k == 1 else (1 - b - k) / (1 - k)
    return c * 255, m * 255, y * 255, k * 255


def cmyk_to_rgb(c, m, y, k):
    c = c / 255
    m = m / 255
    y = y / 255
    k = k / 255
    r = 255 * (1 - c) * (1 - k)
    g = 255 * (1 - m) * (1 - k)
    b = 255 * (1 - y) * (1 - k)
    return r, g, b


rgb_to_cmyk_vector = np.vectorize(rgb_to_cmyk)
cmyk_to_rgb_vector = np.vectorize(cmyk_to_rgb)


def cmy_to_rgba_image(c, m, y, size):
    r, g, b = (Image.fromarray(band.astype("uint8"), "L") for band in cmyk_to_rgb_vector(c, m, y, np.zeros_like(c)))
    a = Image.new("L", size, 255)
    return Image.merge("RGBA", (r, g, b, a))


def to_layer(mask, color):
    color = Image.new("RGBA", mask.size, color)
    alpha = Image.new("RGBA", mask.size)
    return Image.composite(color, alpha, mask=mask)


def blob_mask(color_band):
    band = Image.fromarray(np.clip(color_band, 0, 255).astype("uint8"), "L")
    band = band.convert("1", dither=Image.NONE).convert("L")
    return np.asarray(band).astype("float")


def dither_layer(image, dither_size=2):
    image_size = image.size
    image = image.resize(
        (round(image.width / dither_size), round(image.height / dither_size)),
        Image.ANTIALIAS,
    )
    black = Image.new("LA", (image.width, image.height), (50, 255))
    alpha = Image.new("LA", (image.width, image.height))
    mask = image.convert("L").convert("1", dither=Image.FLOYDSTEINBERG)
    return (
        Image.composite(alpha, black, mask=mask)
        .convert("RGBA")
        .resize(image_size, Image.ANTIALIAS)
    )


def halftone_mask(color_band: Image.Image, angle=0, dot_size=4, supersample=10):
    original_width, original_height = color_band.size

    rotated = color_band.rotate(-angle, expand=True, resample=Image.BICUBIC)

    color_band = Image.new("L", (rotated.width + 2 * dot_size, rotated.height + 2 * dot_size))
    color_band.paste(rotated, (dot_size, dot_size))

    halftone_image = Image.new(
        "L",
        (color_band.width * supersample, color_band.height * supersample),
    )
    draw = ImageDraw.Draw(halftone_image)
    triangle_height = math.sqrt(3) / 2

    look_up_image_a = color_band.resize(
        (
            round(color_band.width / dot_size),
            round((color_band.height / dot_size) / triangle_height),
        )
    )
    look_up_image_b = color_band.transform(
        color_band.size, Image.AFFINE, (1, 0, dot_size / 2, 0, 1, 0)
    ).resize(
        (
            round(color_band.width / dot_size),
            round((color_band.height / dot_size) / triangle_height),
        )
    )

    pixels_a = look_up_image_a.load()
    pixels_b = look_up_image_b.load()

    dot_size *= supersample
    for x in range(look_up_image_a.width):
        for y in range(look_up_image_a.height):
            is_a_row = y % 2 == 0
            if is_a_row:
                color = pixels_a[x, y]
            else:
                color = pixels_b[x, y]
            size = dot_size * (color / 255)
            diff = (dot_size - size) / 2
            shift = is_a_row * (dot_size / 2)
            ul = (x * dot_size + diff + shift, y * (dot_size * triangle_height) + diff)
            lr = ((x + 1) * dot_size - diff + shift, (y + 1) * (dot_size * triangle_height) - diff)
            draw.ellipse([ul, lr], fill=255)

    halftone_image = halftone_image.resize(color_band.size).rotate(angle, resample=Image.BICUBIC)
    left = round((halftone_image.width - original_width) / 2)
    upper = round((halftone_image.height - original_height) / 2)

    return halftone_image.crop((left, upper, left + original_width, upper + original_height))


def halftone_layer(color_band, color, angle, dot_size=4, supersample=10):
    return to_layer(halftone_mask(color_band, angle, dot_size, supersample), color)


def build_preview_image(image):
    array = np.asarray(image.convert("RGB")).astype("float")
    c, m, y, k = [Image.fromarray(band.astype("uint8"), "L") for band in rgb_to_cmyk_vector(*np.rollaxis(array, axis=-1))]

    k = halftone_layer(k, (0, 0, 0, 255), 0)

    image = cmy_to_rgba_image(c, m, y, image.size)
    image.alpha_composite(k)
    return image


def resize_to(image, target_width):
    return image.resize(
        (target_width, round(image.height * target_width / image.width)),
        Image.ANTIALIAS,
    )


@click.command()
@click.argument("source", type=click.Path())
@click.argument("destination", type=click.Path())
def build(source: str, destination: str):
    os.makedirs(destination, exist_ok=True)
    for file_name in os.listdir(source):
        print(file_name)
        base_name, *_ = os.path.splitext(file_name)
        full_name = os.path.join(source, file_name)
        image = Image.open(full_name).convert("RGBA")
        for width, postfix in SIZES:
            new_image = resize_to(image, width)
            new_image.save(os.path.join(destination, f"{base_name}-{postfix}.png"))

            new_image = build_preview_image(new_image)
            new_image.save(os.path.join(destination, f"{base_name}-{postfix}-preview.png"))


if __name__ == "__main__":
    build()
