import click
from PIL import Image, ImageFilter, ImageOps, ImageChops
import numpy as np

import os


SIZES = [(920, "lg"), (460, "md")]

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


def color_layer(image, color_intensity=0.3):
    rgb_to_cmyk_ = np.vectorize(rgb_to_cmyk)
    cmyk_to_rgb_ = np.vectorize(cmyk_to_rgb)

    array = np.asarray(image.convert("RGB")).astype("float")
    c, m, y, _ = rgb_to_cmyk_(*np.rollaxis(array, axis=-1))
    bands = (
        Image.fromarray(np.clip(band / color_intensity, 0, 255).astype("uint8"), "L")
        for band in (c, m, y)
    )
    bands = (band.convert("1", dither=Image.NONE).convert("L") for band in bands)
    bands = (np.asarray(band).astype("float") * color_intensity for band in bands)
    bands = cmyk_to_rgb_(*bands, np.zeros_like(c))
    r, g, b = (Image.fromarray(band.astype("uint8"), "L") for band in bands)

    return Image.merge("RGB", (r, g, b)).convert("RGBA")


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


def build_preview_image(image, target_width):
    image = image.resize(
        (target_width, round(image.height * target_width / image.width)),
        Image.ANTIALIAS,
    )
    color_image = color_layer(image)
    dither = dither_layer(image)
    return Image.alpha_composite(color_image, dither)


def build_image(image, target_width):
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

            new_image = build_preview_image(image, width)
            new_image.save(os.path.join(destination, f"{base_name}-{postfix}-preview.png"))

            new_image = build_image(image, width)
            new_image.save(os.path.join(destination, f"{base_name}-{postfix}.png"))


if __name__ == "__main__":
    build()
