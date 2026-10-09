//! Original bright-area gate, color fill and smoothing; not HitFilm calibration.
use std::cell::RefCell;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 8;
const MAX_PIXELS: usize = 2_097_152;
type Pixel = [f32; 4];
#[derive(Clone, Copy)]
struct Geometry {
    offset: [f64; 2],
    scale: f64,
    size: [f64; 2],
}
struct Image {
    pixels: Vec<Pixel>,
    w: usize,
    h: usize,
    geo: Geometry,
}
fn zeros<T: Clone + Default>(n: usize) -> Result<Vec<T>, ()> {
    let mut v = Vec::new();
    v.try_reserve_exact(n).map_err(|_| ())?;
    v.resize(n, T::default());
    Ok(v)
}
fn valid(p: &[f64], time: f64, scale: f64) -> bool {
    p.len() == FLAT
        && time.is_finite()
        && time.abs() <= 1e9
        && scale.is_finite()
        && (1. / 65536. ..=16.).contains(&scale)
        && p.iter().enumerate().all(|(i, &v)| {
            v.is_finite()
                && match i {
                    0 | 6 => (0. ..=64.).contains(&v),
                    1..=4 => (0. ..=1.).contains(&v),
                    5 => v.abs() <= 64.,
                    7 => (0. ..=8192.).contains(&v),
                    _ => false,
                }
        })
}
include!("helpers.rs");
fn blur(img: &Image, r: f64) -> Result<Vec<Pixel>, ()> {
    let mut out = zeros(img.pixels.len())?;
    if r == 0. {
        out.copy_from_slice(&img.pixels);
        return Ok(out);
    }
    let mut channel = zeros(img.pixels.len())?;
    let mut temp = zeros(img.pixels.len())?;
    let mut result = zeros(img.pixels.len())?;
    for k in 0..4 {
        for (v, c) in channel.iter_mut().zip(&img.pixels) {
            *v = c[k] as f64;
        }
        box_axis(&channel, &mut temp, img.w, img.h, r, true);
        box_axis(&temp, &mut result, img.w, img.h, r, false);
        for (dst, &v) in out.iter_mut().zip(&result) {
            dst[k] = v as f32;
        }
    }
    Ok(out)
}
fn gate(c: Pixel, p: &[f64]) -> Pixel {
    let a = c[3] as f64;
    // Transparent hidden RGB cannot produce a visible highlight.
    let rgb: [f64; 3] = std::array::from_fn(|k| if a > 0. { c[k] as f64 / a } else { 0. });
    let peak = rgb.iter().copied().fold(0., f64::max);
    if peak < p[0] {
        let alpha = a * p[4];
        return [
            (p[1] * alpha) as f32,
            (p[2] * alpha) as f32,
            (p[3] * alpha) as f32,
            alpha as f32,
        ];
    }
    let y = rgb[0] * 0.25 + rgb[1] * 0.5 + rgb[2] * 0.25;
    let color = std::array::from_fn::<_, 3, _>(|k| ((y + (rgb[k] - y) * p[5]) * p[6] * a) as f32);
    [color[0], color[1], color[2], c[3]]
}
fn render(main: &Image, p: &[f64], time: f64, scale: f64) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale)
        || main.w.checked_mul(main.h) != Some(main.pixels.len())
        || main.pixels.is_empty()
        || main.pixels.len() > MAX_PIXELS
        || main.geo.scale != scale
        || main.geo.offset.iter().any(|v| !v.is_finite())
        || main.geo.size.iter().any(|v| !v.is_finite() || *v <= 0.)
        || main.pixels.iter().any(|c| {
            c.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0. ..=1.).contains(&c[3])
        })
    {
        return Err(());
    }
    let mut out = blur(main, p[7] * scale)?;
    for c in &mut out {
        *c = gate(*c, p);
        if c.iter().any(|v| !v.is_finite()) {
            return Err(());
        }
    }
    Ok(out)
}
include!("abi.rs");
#[cfg(test)]
mod tests;
