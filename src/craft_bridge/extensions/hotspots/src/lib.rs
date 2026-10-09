//! Original highlight extraction with explicit mask, not Sapphire calibration.
use std::cell::RefCell;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 15;
const MAX_PIXELS: usize = 2_097_152;
type Pixel = [f32; 4];
#[derive(Clone, Copy)]
struct Geometry {
    offset: [f64; 2],
    scale: f64,
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
                    0 | 1 => v.fract() == 0. && (0. ..=u32::MAX as f64).contains(&v),
                    2 | 11 => v.fract() == 0. && (0. ..=2.).contains(&v),
                    3 | 13 => (0. ..=8192.).contains(&v),
                    4 | 10 => (0. ..=64.).contains(&v),
                    5..=8 => (0. ..=1.).contains(&v),
                    9 => v.abs() <= 64.,
                    12 | 14 => v == 0. || v == 1.,
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
fn extract(c: Pixel, p: &[f64]) -> Pixel {
    let alpha = if p[11] == 0. { 1. } else { c[3] as f64 };
    let rgb: [f64; 3] = std::array::from_fn(|k| {
        if p[11] == 1. {
            if alpha > 0. { c[k] as f64 / alpha } else { 0. }
        } else {
            c[k] as f64
        }
    });
    let peak = rgb.iter().copied().fold(0., f64::max);
    let bias = if peak > 0. {
        (0..3)
            .map(|k| rgb[k].max(0.) / peak * p[5 + k])
            .sum::<f64>()
    } else {
        0.
    };
    let strength = if peak > 0. {
        (1. - (p[4] + bias) / peak).max(0.)
    } else {
        0.
    };
    let scaled = rgb.map(|v| v * strength);
    let y = scaled[0] * 0.25 + scaled[1] * 0.5 + scaled[2] * 0.25;
    let color = std::array::from_fn::<_, 3, _>(|k| (y + (scaled[k] - y) * p[9]) * p[10]);
    let gain = if p[11] == 1. { alpha } else { 1. };
    [
        (color[0] * gain) as f32,
        (color[1] * gain) as f32,
        (color[2] * gain) as f32,
        alpha as f32,
    ]
}
fn render(
    main: &Image,
    mask: Option<&Image>,
    p: &[f64],
    time: f64,
    scale: f64,
) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale)
        || main.w == 0
        || main.h == 0
        || main.w.checked_mul(main.h) != Some(main.pixels.len())
        || main.pixels.len() > MAX_PIXELS
        || mask.is_some_and(|m| {
            m.w == 0
                || m.h == 0
                || m.w.checked_mul(m.h) != Some(m.pixels.len())
                || m.pixels.len() > MAX_PIXELS
        })
    {
        return Err(());
    }
    let input = blur(main, p[3] * scale)?;
    let mask_blurred = if let Some(m) = mask {
        Some(Image {
            pixels: blur(m, p[13] * m.geo.scale)?,
            w: m.w,
            h: m.h,
            geo: m.geo,
        })
    } else {
        None
    };
    let mut out = zeros(input.len())?;
    for (i, dst) in out.iter_mut().enumerate() {
        let transformed = extract(input[i], p);
        let amount = if let Some(mask) = mask_blurred.as_ref() {
            let world = [
                ((i % main.w) as f64 + 0.5 - main.geo.offset[0]) / scale,
                ((i / main.w) as f64 + 0.5 - main.geo.offset[1]) / scale,
            ];
            let c = sample(Some(mask), world);
            let v = if p[12] == 1. {
                c[3] as f64
            } else {
                c[0] as f64 * 0.25 + c[1] as f64 * 0.5 + c[2] as f64 * 0.25
            }
            .clamp(0., 1.);
            if p[14] == 1. { 1. - v } else { v }
        } else {
            1.
        };
        *dst = std::array::from_fn(|k| {
            (main.pixels[i][k] as f64 * (1. - amount) + transformed[k] as f64 * amount) as f32
        });
    }
    if out.iter().flatten().all(|v| v.is_finite()) {
        Ok(out)
    } else {
        Err(())
    }
}
include!("abi.rs");
#[cfg(test)]
mod tests;
