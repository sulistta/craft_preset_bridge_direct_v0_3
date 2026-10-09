//! Original mathematical tile/glyph painter, no proprietary patterns or units.
use std::cell::RefCell;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 22;
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
                    0 => v.fract() == 0. && (0. ..=9.).contains(&v),
                    1 => v.abs() <= 100.,
                    2 | 5 | 6 => (0. ..=1000.).contains(&v),
                    3 => (0.1..=1024.).contains(&v),
                    4 | 15..=17 => v == 0. || v == 1.,
                    7..=14 => (0. ..=1.).contains(&v),
                    18 => (0. ..=100.).contains(&v),
                    19 => v.abs() <= 10000.,
                    20 => v.abs() <= 1e9,
                    21 => v.fract() == 0. && (0. ..=2.).contains(&v),
                    _ => false,
                }
        })
}
fn random(seed: f64, x: i64, y: i64, frame: i64) -> f64 {
    let mut n = seed.to_bits()
        ^ (x as u64).wrapping_mul(0x9e3779b97f4a7c15)
        ^ (y as u64).wrapping_mul(0xbf58476d1ce4e5b9)
        ^ (frame as u64).wrapping_mul(0x94d049bb133111eb);
    n ^= n >> 30;
    n = n.wrapping_mul(0xbf58476d1ce4e5b9);
    n ^= n >> 27;
    n = n.wrapping_mul(0x94d049bb133111eb);
    n ^= n >> 31;
    (n >> 11) as f64 / ((1u64 << 53) - 1) as f64
}
fn sample(img: &Image, at: [f64; 2]) -> Pixel {
    let x = (at[0] * img.geo.scale + img.geo.offset[0] - 0.5)
        .round()
        .clamp(0., img.w as f64 - 1.) as usize;
    let y = (at[1] * img.geo.scale + img.geo.offset[1] - 0.5)
        .round()
        .clamp(0., img.h as f64 - 1.) as usize;
    img.pixels[y * img.w + x]
}
// Seven mathematical segments plus a crossbar create our own digits/letters.
fn glyph(x: f64, y: f64, tone: f64) -> bool {
    const MASK: [u8; 18] = [
        0x3f, 0x06, 0x5b, 0x4f, 0x66, 0x6d, 0x7d, 0x07, 0x7f, 0x6f, 0x77, 0x39, 0x79, 0x71, 0x76,
        0x38, 0x73, 0x3e,
    ];
    let mask = MASK[(tone * 17.).floor().clamp(0., 17.) as usize];
    let width = 0.04 + tone * 0.045;
    let horizontal = |at: f64| (y - at).abs() <= width && x.abs() <= 0.3;
    let vertical = |at: f64, lo: f64, hi: f64| (x - at).abs() <= width && (lo..=hi).contains(&y);
    let hits = [
        horizontal(-0.4),
        vertical(0.3, -0.4, 0.),
        vertical(0.3, 0., 0.4),
        horizontal(0.4),
        vertical(-0.3, 0., 0.4),
        vertical(-0.3, -0.4, 0.),
        horizontal(0.),
    ];
    hits.iter()
        .enumerate()
        .any(|(i, hit)| *hit && mask & (1 << i) != 0)
}
fn pattern(shape: usize, x: f64, y: f64, tone: f64, noise: f64) -> bool {
    if tone <= 0. || x.abs() > 0.5 || y.abs() > 0.5 {
        return false;
    }
    match shape {
        0 => {
            let ix = ((x + 0.5) * 4.).floor().clamp(0., 3.) as usize;
            let iy = ((y + 0.5) * 4.).floor().clamp(0., 3.) as usize;
            (((ix * 5 + iy * 3) % 16) as f64 + 0.5) / 16. < tone
        }
        1 => glyph(x, y, tone),
        2 => y.abs() <= tone * 0.5,
        3 => x * x + y * y <= tone * 0.25,
        4 => x.abs() <= tone * 0.5,
        5 => noise < tone,
        6 => ((x * x + y * y).sqrt() - 0.35).abs() <= tone * 0.15,
        7 => x.abs().max(y.abs()) <= tone.sqrt() * 0.5,
        8 => (x + y).abs() <= tone * 0.5,
        9 => (x - y).abs() <= tone * 0.5,
        _ => false,
    }
}
fn render(img: &Image, p: &[f64], time: f64, scale: f64) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale)
        || img.w == 0
        || img.h == 0
        || img.geo.size.iter().any(|v| !v.is_finite() || *v <= 0.)
        || img.w.checked_mul(img.h) != Some(img.pixels.len())
        || img.pixels.len() > MAX_PIXELS
    {
        return Err(());
    }
    let mut out = zeros(img.pixels.len())?;
    let cw = p[3] * 100. / p[5].max(0.1);
    let ch = if p[4] == 1. {
        cw
    } else {
        p[3] * 100. / p[6].max(0.1)
    };
    let frame = if p[17] == 1. {
        (time * p[19]).floor() as i64
    } else {
        0
    };
    for (i, dst) in out.iter_mut().enumerate() {
        let world = [
            ((i % img.w) as f64 + 0.5 - img.geo.offset[0]) / img.geo.scale,
            ((i / img.w) as f64 + 0.5 - img.geo.offset[1]) / img.geo.scale,
        ];
        let cell = [
            (world[0] / cw).floor() as i64,
            (world[1] / ch).floor() as i64,
        ];
        let source = sample(
            img,
            [(cell[0] as f64 + 0.5) * cw, (cell[1] as f64 + 0.5) * ch],
        );
        let luma = source[0] as f64 * 0.25 + source[1] as f64 * 0.5 + source[2] as f64 * 0.25;
        let tone = ((luma - 0.5) * p[2] / 100. + 0.5 + p[1] / 100.).clamp(0., 1.);
        let chaos = if p[17] == 1. {
            random(p[20], cell[0], cell[1], frame) * p[18] / 100.
        } else {
            0.
        };
        let size = match p[21] as usize {
            0 => 1. + chaos,
            1 => 1. - chaos,
            2 => 1. + (chaos * 2. - p[18] / 100.) * f64::from(p[17] == 1.),
            _ => 1.,
        }
        .max(0.01);
        let x = (world[0] / cw - cell[0] as f64 - 0.5) / size;
        let y = (world[1] / ch - cell[1] as f64 - 0.5) / size;
        let noise = random(
            p[20],
            (x * 32.).floor() as i64 + cell[0] * 37,
            (y * 32.).floor() as i64 + cell[1] * 37,
            frame,
        );
        let hit = pattern(p[0] as usize, x, y, tone, noise);
        let color = if hit {
            if p[15] == 1. {
                source
            } else {
                std::array::from_fn(|k| p[7 + k] as f32)
            }
        } else {
            std::array::from_fn(|k| p[11 + k] as f32)
        };
        *dst = if !hit && p[16] == 1. {
            [0.; 4]
        } else {
            [color[0], color[1], color[2], color[3] * img.pixels[i][3]]
        };
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
