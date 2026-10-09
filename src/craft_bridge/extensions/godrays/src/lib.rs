//! Original radial/spin integration. Source raw sliders are not certified units.
use std::cell::RefCell;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 26;
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
                    0 | 3 | 19 => v.fract() == 0. && (0. ..=1.).contains(&v),
                    1 | 2 => v.abs() <= 1.016e9,
                    4 | 5 | 11 | 15 | 18 => (0. ..=100.).contains(&v),
                    6 => (0. ..=100000.).contains(&v),
                    7 => v.abs() <= 360000.,
                    8 => v.abs() <= 20.,
                    9 => v.abs() <= 10.,
                    10 | 12 | 21 => v.fract() == 0. && (0. ..=2.).contains(&v),
                    13 => v.fract() == 0. && (0. ..=4.).contains(&v),
                    14 => (2. ..=256.).contains(&v),
                    16 | 20 => v == 0. || v == 1.,
                    17 => v == 0.,
                    22..=25 => (0. ..=8192.).contains(&v),
                    _ => false,
                }
        })
}
fn world(img: &Image, i: usize) -> [f64; 2] {
    [
        ((i % img.w) as f64 + 0.5 - img.geo.offset[0]) / img.geo.scale,
        ((i / img.w) as f64 + 0.5 - img.geo.offset[1]) / img.geo.scale,
    ]
}
fn center(img: &Image, p: &[f64]) -> Result<[f64; 2], ()> {
    // The pinned host flattens Point via Buf::to_px, even when the stored
    // coordinates are raw source coefficients. Recover that stored value.
    let position = [
        (p[1] - img.geo.offset[0]) / img.geo.scale,
        (p[2] - img.geo.offset[1]) / img.geo.scale,
    ];
    if position.iter().any(|v| !v.is_finite() || v.abs() > 1e6) {
        return Err(());
    }
    Ok([
        img.geo.size[0] * (0.5 + position[0]),
        img.geo.size[1] * (0.5 + position[1]),
    ])
}
fn cropped(at: [f64; 2], size: [f64; 2], p: &[f64]) -> bool {
    (p[22] > 0. && at[0] < p[22])
        || (p[23] > 0. && at[1] < p[23])
        || (p[24] > 0. && at[0] >= size[0] - p[24])
        || (p[25] > 0. && at[1] >= size[1] - p[25])
}
fn clean(px: Pixel) -> Pixel {
    if px[3] == 0. { [0.; 4] } else { px }
}
fn gate(px: Pixel, p: &[f64]) -> Pixel {
    if px[3] == 0. {
        return [0.; 4];
    }
    let rgb: [f64; 3] = std::array::from_fn(|k| px[k] as f64 / px[3] as f64);
    let metric = if p[3] == 0. {
        0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    } else {
        rgb.iter().copied().fold(f64::NEG_INFINITY, f64::max)
            - rgb.iter().copied().fold(f64::INFINITY, f64::min)
    };
    let threshold = p[4] / 100.;
    let factor = if p[5] == 0. {
        f64::from(metric >= threshold)
    } else {
        let t = ((metric - threshold) / (p[5] / 100.)).clamp(0., 1.);
        t * t * (3. - 2. * t)
    };
    std::array::from_fn(|k| (px[k] as f64 * factor) as f32)
}
fn sample(img: &Image, at: [f64; 2], repeat: bool) -> Pixel {
    let mut x = at[0] * img.geo.scale + img.geo.offset[0] - 0.5;
    let mut y = at[1] * img.geo.scale + img.geo.offset[1] - 0.5;
    if repeat {
        x = x.clamp(0., img.w as f64 - 1.);
        y = y.clamp(0., img.h as f64 - 1.);
    } else if x <= -1. || y <= -1. || x >= img.w as f64 || y >= img.h as f64 {
        return [0.; 4];
    }
    let ix = x.floor() as isize;
    let iy = y.floor() as isize;
    let dx = x - ix as f64;
    let dy = y - iy as f64;
    let get = |a: isize, b: isize| {
        if a < 0 || b < 0 || a >= img.w as isize || b >= img.h as isize {
            [0.; 4]
        } else {
            img.pixels[b as usize * img.w + a as usize]
        }
    };
    let values = [
        get(ix, iy),
        get(ix + 1, iy),
        get(ix, iy + 1),
        get(ix + 1, iy + 1),
    ];
    let weights = [
        (1. - dx) * (1. - dy),
        dx * (1. - dy),
        (1. - dx) * dy,
        dx * dy,
    ];
    std::array::from_fn(|k| {
        values
            .iter()
            .zip(weights)
            .map(|(v, w)| v[k] as f64 * w)
            .sum::<f64>() as f32
    })
}
fn path(at: [f64; 2], center: [f64; 2], p: &[f64], t: f64, sign: f64) -> [f64; 2] {
    let d = [at[0] - center[0], at[1] - center[1]];
    if p[0] == 1. {
        let factor = 1. - sign * t * p[6] / 10000.;
        [center[0] + d[0] * factor, center[1] + d[1] * factor]
    } else {
        let angle = -sign * t * p[7].to_radians();
        let (s, c) = angle.sin_cos();
        [
            center[0] + d[0] * c - d[1] * s,
            center[1] + d[0] * s + d[1] * c,
        ]
    }
}
fn random(x: i64, y: i64, tap: usize) -> f64 {
    let mut n = (x as u64).wrapping_mul(0x9e3779b97f4a7c15)
        ^ (y as u64).wrapping_mul(0xbf58476d1ce4e5b9)
        ^ (tap as u64).wrapping_mul(0x94d049bb133111eb);
    n ^= n >> 30;
    n = n.wrapping_mul(0xbf58476d1ce4e5b9);
    n ^= n >> 27;
    n = n.wrapping_mul(0x94d049bb133111eb);
    n ^= n >> 31;
    (n >> 11) as f64 / ((1u64 << 53) - 1) as f64
}
fn count(p: &[f64]) -> usize {
    match p[13] as usize {
        0 => 8,
        1 => 16,
        2 => 32,
        3 => 64,
        _ => p[14].round() as usize,
    }
}
fn finish(mut ray: Pixel, p: &[f64]) -> Pixel {
    let gain = p[8].exp2();
    for v in &mut ray[..3] {
        *v = (*v as f64 * gain) as f32;
    }
    if p[20] == 1. {
        ray[3] = ray[..3].iter().copied().fold(0., f32::max).clamp(0., 1.);
    }
    clean(ray)
}
fn rays(img: &Image, at: [f64; 2], center: [f64; 2], p: &[f64]) -> Pixel {
    let n = count(p);
    let signs: &[f64] = match p[10] as usize {
        0 => &[1.],
        1 => &[-1.],
        _ => &[1., -1.],
    };
    let pair = match p[12] as usize {
        0 => [0, 2],
        1 => [0, 1],
        _ => [1, 2],
    };
    let chromatic = p[11] / 100. * 0.05;
    let mut sum = [0.; 4];
    let mut total = 0.;
    for j in 0..n {
        let jitter = if j == 0 || j == n - 1 {
            0.
        } else {
            (random(at[0].floor() as i64, at[1].floor() as i64, j) - 0.5) * p[15] / 100.
        };
        let t = (j as f64 + jitter) / (n - 1) as f64;
        let weight = (-p[9] * t).exp();
        for &sign in signs {
            let mut color = sample(img, path(at, center, p, t, sign), p[16] == 1.);
            if chromatic > 0. {
                for (channel, offset) in pair.into_iter().zip([-chromatic, chromatic]) {
                    let shifted = sample(img, path(at, center, p, t + offset, sign), p[16] == 1.);
                    color[channel] = shifted[channel];
                    color[3] = color[3].max(shifted[3]);
                }
            }
            for k in 0..4 {
                sum[k] += color[k] as f64 * weight;
            }
            total += weight;
        }
    }
    finish(std::array::from_fn(|k| (sum[k] / total) as f32), p)
}
fn compose(input: Pixel, processed: Pixel, ray: Pixel, p: &[f64]) -> Pixel {
    if p[21] == 1. {
        return ray;
    }
    let opacity = p[18] / 100.;
    if p[21] == 0. {
        return std::array::from_fn(|k| (processed[k] as f64 * opacity) as f32);
    }
    let base = clean(input);
    std::array::from_fn(|k| {
        let a = base[k] as f64 * opacity;
        let b = ray[k] as f64;
        (if k == 3 || p[19] == 0. {
            a + b - a * b
        } else {
            a + b
        }) as f32
    })
}
fn render(img: &Image, p: &[f64], time: f64, scale: f64) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale)
        || img.w == 0
        || img.h == 0
        || img.w.checked_mul(img.h) != Some(img.pixels.len())
        || img.pixels.len() > MAX_PIXELS
        || img.w > 65536
        || img.h > 65536
        || img.geo.scale != scale
        || img
            .geo
            .offset
            .iter()
            .any(|v| !v.is_finite() || v.abs() > 1e9)
        || img
            .geo
            .size
            .iter()
            .any(|v| !v.is_finite() || !(f64::MIN_POSITIVE..=1e9).contains(v))
        || img.pixels.iter().any(|px| {
            px.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0. ..=1.).contains(&px[3])
        })
    {
        return Err(());
    }
    let center = center(img, p)?;
    let mut processed = zeros(img.pixels.len())?;
    for (i, dst) in processed.iter_mut().enumerate() {
        *dst = if cropped(world(img, i), img.geo.size, p) {
            [0.; 4]
        } else {
            gate(img.pixels[i], p)
        };
    }
    let source = Image {
        pixels: processed,
        w: img.w,
        h: img.h,
        geo: img.geo,
    };
    let mut out = zeros(img.pixels.len())?;
    // Clamp sampling of an exactly uniform processed buffer stays uniform for
    // every radial/spin/chromatic path. This is an algebraic fast path.
    let constant = p[16] == 1. && source.pixels.iter().all(|px| *px == source.pixels[0]);
    let uniform_ray = if constant {
        finish(source.pixels[0], p)
    } else {
        [0.; 4]
    };
    for (i, dst) in out.iter_mut().enumerate() {
        let ray = if constant {
            uniform_ray
        } else {
            rays(&source, world(img, i), center, p)
        };
        *dst = compose(img.pixels[i], source.pixels[i], ray, p);
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
