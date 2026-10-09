//! Original analog-style modulation/decoding. No proprietary algorithm or units.
use std::cell::RefCell;
use std::f64::consts::TAU;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 34;
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
                    0 => (0. ..=1e9).contains(&v),
                    2 => (0. ..=64.).contains(&v),
                    6 => (0. ..=10000.).contains(&v),
                    7 | 17..=19 => (0. ..=1.).contains(&v),
                    9 => (0. ..=16.).contains(&v),
                    10 | 27 => v.fract() == 0. && (0. ..=2.).contains(&v),
                    11 | 16 | 26 | 30..=32 => v == 0. || v == 1.,
                    12 | 24 | 25 => v.abs() <= 10000.,
                    13 | 28 | 29 => v.abs() <= 1e6,
                    14 | 22 | 23 => v.abs() <= 100.,
                    _ => (0. ..=100.).contains(&v),
                }
        })
}
// Exactly invertible opponent transform; intentionally not a standard color space.
fn encode(c: Pixel) -> [f64; 3] {
    let [r, g, b, _] = c.map(f64::from);
    [r * 0.25 + g * 0.5 + b * 0.25, r - b, g - (r + b) * 0.5]
}
fn decode(c: [f64; 3], alpha: f32) -> Pixel {
    let [y, i, q] = c;
    [
        (y - q * 0.5 + i * 0.5) as f32,
        (y + q * 0.5) as f32,
        (y - q * 0.5 - i * 0.5) as f32,
        alpha,
    ]
}
fn random(seed: f64, x: i64, y: i64, frame: i64, channel: u64) -> f64 {
    let mut n = seed.to_bits()
        ^ (x as u64).wrapping_mul(0x9e3779b97f4a7c15)
        ^ (y as u64).wrapping_mul(0xbf58476d1ce4e5b9)
        ^ (frame as u64).wrapping_mul(0x94d049bb133111eb)
        ^ channel;
    n ^= n >> 30;
    n = n.wrapping_mul(0xbf58476d1ce4e5b9);
    n ^= n >> 27;
    n = n.wrapping_mul(0x94d049bb133111eb);
    n ^= n >> 31;
    (n >> 11) as f64 / ((1u64 << 53) - 1) as f64
}
fn periodic_sample(img: &Image, x: f64, y: f64) -> Pixel {
    let x = x.rem_euclid(img.w as f64);
    let y = y.rem_euclid(img.h as f64);
    let (ix, iy) = (x.floor() as usize, y.floor() as usize);
    let (fx, fy) = (x - x.floor(), y - y.floor());
    let mut out = [0.; 4];
    for (dy, wy) in [(0, 1. - fy), (1, fy)] {
        for (dx, wx) in [(0, 1. - fx), (1, fx)] {
            let c = img.pixels[((iy + dy) % img.h) * img.w + (ix + dx) % img.w];
            for k in 0..4 {
                out[k] += (c[k] as f64 * wx * wy) as f32;
            }
        }
    }
    out
}
fn smooth(v: f64) -> f64 {
    let v = v.clamp(0., 1.);
    v * v * (3. - 2. * v)
}
fn tape_amount(p: &[f64], y: f64, time: f64) -> f64 {
    if p[16] == 0.
        || p[18] < p[17]
        || y < p[17]
        || y > p[18]
        || random(p[0], 0, 0, (time * 30.).floor() as i64, 0x74617065) >= p[19]
    {
        return 0.;
    }
    let edge = (y - p[17]).min(p[18] - y);
    let fade = p[20] / 100.;
    let a = if fade == 0. { 1. } else { smooth(edge / fade) };
    a.powf(p[21].max(0.001))
}
fn render(img: &Image, p: &[f64], time: f64, scale: f64) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale)
        || img.w == 0
        || img.h == 0
        || img.pixels.len() != img.w * img.h
        || img.pixels.len() > MAX_PIXELS
    {
        return Err(());
    }
    let mut out: Vec<Pixel> = zeros(img.pixels.len())?;
    if p[1] == 0. {
        out.copy_from_slice(&img.pixels);
        return Ok(out);
    }
    let mut channels: Vec<[f64; 3]> = zeros(img.pixels.len())?;
    let frame = (time * 30.).floor() as i64;
    // First stage: geometry, opponent channels, noise, dropout, luma modulation.
    for (index, c) in channels.iter_mut().enumerate() {
        let (x, y) = (index % img.w, index / img.w);
        let qx = (x as f64 + 0.5 - img.geo.offset[0]) / scale;
        let qy = (y as f64 + 0.5 - img.geo.offset[1]) / scale;
        let ny = qy / img.geo.size[1];
        let t = time * p[24] / 100.;
        let dx = img.geo.size[0] / 100.
            * (p[22] * (TAU * (ny * 3. + t)).sin() + p[23] * (TAU * (ny * 83. + t * 7.)).sin());
        let dy = time * p[25] / 100. * img.geo.size[1];
        *c = encode(periodic_sample(
            img,
            x as f64 + dx * scale,
            y as f64 + dy * scale,
        ));
        let noise = |ch| 2. * random(p[0], qx.floor() as i64, qy.floor() as i64, frame, ch) - 1.;
        c[0] += noise(1) * p[4] / 100.;
        c[1] += noise(2) * p[5] / 100.;
        c[2] += noise(3) * p[5] / 100.;
        let angle = TAU * (noise(4) * p[6] + p[28] + p[29] * ny) / 360.;
        let (s, co) = angle.sin_cos();
        let (i, q) = (c[1], c[2]);
        let keep = (1. - p[7]) * (-p[9] * 0.06).exp();
        c[1] = (i * co - q * s) * keep;
        c[2] = (i * s + q * co) * keep;
        if p[11] == 1. {
            c[0] *= 1. + p[14] * (TAU * (ny * p[12] * 8. + time * p[12] + p[13] / 360.)).sin();
        }
        if p[15] > 0. {
            let levels = (256. - p[15] * 2.54).max(2.);
            c[0] = (c[0] * levels).round() / levels;
        }
        let a = tape_amount(p, ny, time);
        c[0] = c[0] * (1. - a) + noise(5) * a * 0.25;
        c[1] *= 1. - a;
        c[2] *= 1. - a;
    }
    // One scanline at a time: four carrier samples/pixel, bounded receiver FIR.
    let mut signal: Vec<f64> = zeros(img.w * 4)?;
    let mut luma: Vec<f64> = zeros(img.w)?;
    const COS: [f64; 4] = [1., 0., -1., 0.];
    const SIN: [f64; 4] = [0., 1., 0., -1.];
    let input_radius = [1isize, 2, 4][p[10] as usize];
    for y in 0..img.h {
        for x in 0..img.w {
            let at = |dx: isize, dy: isize| {
                channels[(y as isize + dy).rem_euclid(img.h as isize) as usize * img.w
                    + (x as isize + dx).rem_euclid(img.w as isize) as usize]
            };
            let mut c = at(0, 0);
            let left = at(-input_radius, 0);
            let right = at(input_radius, 0);
            let vup = at(0, -1);
            let vdown = at(0, 1);
            let blur = if p[26] == 1. {
                (1. - p[3] / 100.) * (1. + p[10] * 0.5)
            } else {
                0.
            };
            for k in 0..3 {
                c[k] += ((left[k] + right[k]) * 0.5 - c[k]) * blur.clamp(0., 1.);
                let vb = if k == 0 {
                    p[33] / 100.
                } else {
                    f64::from(p[31] == 1.) * 0.5
                };
                c[k] += ((vup[k] + vdown[k]) * 0.5 - c[k]) * vb;
            }
            c[0] += ((left[0] + right[0]) * 0.5 - c[0]) * p[9] / 100.;
            if p[32] == 1. {
                c[0] += (at(0, 0)[0] - (left[0] + right[0]) * 0.5) * p[8] / 10.;
            }
            c[0] *= p[2];
            luma[x] = c[0];
            for k in 0..4 {
                signal[x * 4 + k] = f64::from(p[30] == 0.) * c[0] + c[1] * COS[k] + c[2] * SIN[k];
            }
        }
        let radius = [0isize, 1, 3][p[27] as usize];
        for (x, &source_luma) in luma.iter().enumerate() {
            let mut decoded = [0.; 3];
            for k in 0..4 {
                let center = x * 4 + k;
                let mut v = 0.;
                let mut total = 0.;
                for tap in -radius..=radius {
                    let weight = (radius + 1 - tap.abs()) as f64;
                    let pos = (center as isize + tap).rem_euclid(signal.len() as isize) as usize;
                    v += signal[pos] * weight;
                    total += weight;
                }
                v = signal[center] * 0.25 + v / total * 0.75;
                decoded[0] += v * 0.25;
                decoded[1] += v * COS[k] * 0.5;
                decoded[2] += v * SIN[k] * 0.5;
            }
            if p[30] == 1. {
                decoded[0] = source_luma;
            }
            let original = img.pixels[y * img.w + x];
            let processed = decode(decoded, original[3]);
            let strength = p[1] / 100.;
            out[y * img.w + x] = std::array::from_fn(|k| {
                if k == 3 {
                    original[3]
                } else {
                    (original[k] as f64 * (1. - strength) + processed[k] as f64 * strength) as f32
                }
            });
        }
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
