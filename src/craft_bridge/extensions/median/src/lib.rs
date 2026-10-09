//! Original bounded oriented neighborhood median for EffectCraft API v1.
//! Independent approximation; no source plugin code or assets. See ADR 022.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 10;
const MAX_PIXELS: usize = 8_388_608;
const MAX_SIDE: usize = 65_536;

thread_local! {
    static HOST: RefCell<Vec<u64>> = const { RefCell::new(Vec::new()) };
}

#[unsafe(no_mangle)]
pub extern "C" fn ec_api_version() -> i32 {
    1
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_manifest_ptr() -> i32 {
    MANIFEST.as_ptr() as i32
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_manifest_len() -> i32 {
    MANIFEST.len() as i32
}

#[unsafe(no_mangle)]
pub extern "C" fn ec_alloc(bytes: i32) -> i32 {
    if bytes <= 0 || bytes as usize > MAX_PIXELS * 16 + FLAT_PARAMS * 8 {
        return 0;
    }
    HOST.with(|buf| {
        let mut buf = buf.borrow_mut();
        let additional = (bytes as usize).div_ceil(8).saturating_sub(buf.len());
        if buf.try_reserve(additional).is_err() {
            return 0;
        }
        buf.resize((bytes as usize).div_ceil(8), 0);
        buf.as_mut_ptr() as i32
    })
}

/// The ABI pointers must reference the allocation returned by ec_alloc.
/// Validate both ranges and alignment before forming slices. Invalid calls leave it intact.
#[unsafe(no_mangle)]
pub extern "C" fn ec_render(
    pixels: i32,
    width: i32,
    height: i32,
    params: i32,
    nparams: i32,
    _time: f64,
    scale: f64,
) -> i32 {
    if width <= 0 || height <= 0 || nparams != FLAT_PARAMS as i32 {
        return 1;
    }
    let Some(n) = (width as usize)
        .checked_mul(height as usize)
        .filter(|n| *n <= MAX_PIXELS)
    else {
        return 1;
    };
    HOST.with(|buf| {
        let mut buf = buf.borrow_mut();
        let start = buf.as_mut_ptr() as usize;
        let end = start + buf.len() * 8;
        let pp = params as u32 as usize;
        let xp = pixels as u32 as usize;
        if pp != start
            || xp != start + FLAT_PARAMS * 8
            || xp.checked_add(n * 16).is_none_or(|v| v > end)
        {
            return 1;
        }
        // Ranges are aligned, disjoint, inside HOST and the borrow prevents reallocations.
        let p = unsafe { std::slice::from_raw_parts(pp as *const f64, FLAT_PARAMS) };
        let px = unsafe { std::slice::from_raw_parts_mut(xp as *mut [f32; 4], n) };
        match render(px, width as usize, height as usize, p, scale) {
            Ok(()) => 0,
            Err(()) => 1,
        }
    })
}

const MAX_TAPS: usize = 36;
fn valid(p: &[f64], scale: f64) -> bool {
    p.len() == FLAT_PARAMS
        && p.iter().all(|v| v.is_finite())
        && scale.is_finite()
        && (1.0 / MAX_SIDE as f64..=16.0).contains(&scale)
        && [0.0, 1.0, 2.0, 3.0].contains(&p[0])
        && (0.0..=8.0).contains(&p[1])
        && p[1].fract() == 0.0
        && [0.0, 1.0].contains(&p[2])
        && [0.0, 1.0].contains(&p[6])
        && [3, 4].iter().all(|i| (0.0..=512.0).contains(&p[*i]))
        && p[5].abs() <= 36000.0
        && [7, 8, 9].iter().all(|i| (0.0..=100.0).contains(&p[*i]))
}
fn allocate<T: Clone>(n: usize, value: T) -> Result<Vec<T>, ()> {
    let mut v = Vec::new();
    v.try_reserve_exact(n).map_err(|_| ())?;
    v.resize(n, value);
    Ok(v)
}
fn odd(v: usize) -> usize {
    if v.is_multiple_of(2) {
        v.saturating_sub(1).max(1)
    } else {
        v.max(1)
    }
}
fn kernel(rx: usize, ry: usize, angle: f64, limit: usize) -> Result<Vec<(i32, i32)>, ()> {
    let mut nx = odd((2 * rx + 1).min(limit));
    let mut ny = odd((2 * ry + 1).min(limit));
    if nx * ny > limit {
        let factor = (limit as f64 / (nx * ny) as f64).sqrt();
        nx = odd((nx as f64 * factor).floor() as usize).max(if rx > 0 { 3 } else { 1 });
        ny = odd((ny as f64 * factor).floor() as usize).max(if ry > 0 { 3 } else { 1 });
    }
    if nx * ny > limit {
        if nx >= ny {
            nx = odd(limit / ny);
        } else {
            ny = odd(limit / nx);
        }
    }
    let mut offsets = Vec::new();
    offsets.try_reserve_exact(nx * ny).map_err(|_| ())?;
    let (sin, cos) = angle.rem_euclid(360.0).to_radians().sin_cos();
    for y in 0..ny {
        for x in 0..nx {
            let a = if nx == 1 {
                0.0
            } else {
                2.0 * rx as f64 * x as f64 / (nx - 1) as f64 - rx as f64
            };
            let b = if ny == 1 {
                0.0
            } else {
                2.0 * ry as f64 * y as f64 / (ny - 1) as f64 - ry as f64
            };
            offsets.push((
                (a * cos - b * sin).round() as i32,
                (a * sin + b * cos).round() as i32,
            ));
        }
    }
    // Spatial ties prefer nearer samples. Repeated offsets retain their multiplicity.
    offsets.sort_unstable_by_key(|(x, y)| (i64::from(*x).pow(2) + i64::from(*y).pow(2), *y, *x));
    Ok(offsets)
}
fn hsv(px: [f32; 4]) -> [f64; 3] {
    let c: [f64; 3] = std::array::from_fn(|i| (px[i] as f64).max(0.0));
    let hi = c.into_iter().fold(0.0, f64::max);
    let lo = c.into_iter().fold(f64::INFINITY, f64::min);
    let d = hi - lo;
    let hue = if d == 0.0 {
        0.0
    } else if hi == c[0] {
        (c[1] - c[2]) / d
    } else if hi == c[1] {
        (c[2] - c[0]) / d + 2.0
    } else {
        (c[0] - c[1]) / d + 4.0
    };
    [
        (hue / 6.0).rem_euclid(1.0),
        if hi == 0.0 { 0.0 } else { d / hi },
        hi,
    ]
}
fn from_hsv(h: f64, s: f64, v: f64) -> [f32; 3] {
    let h = h.rem_euclid(1.0) * 6.0;
    let c = v * s.clamp(0.0, 1.0);
    let x = c * (1.0 - (h.rem_euclid(2.0) - 1.0).abs());
    let channels = match h as u8 {
        0 => [c, x, 0.0],
        1 => [x, c, 0.0],
        2 => [0.0, c, x],
        3 => [0.0, x, c],
        4 => [x, 0.0, c],
        _ => [c, 0.0, x],
    };
    channels.map(|a| (a + v - c) as f32)
}
fn metric(px: [f32; 4], channel: usize) -> f32 {
    match channel {
        0 => (0.2126 * px[0] as f64 + 0.7152 * px[1] as f64 + 0.0722 * px[2] as f64) as f32,
        1 => {
            let lo = px[..3].iter().copied().fold(f32::INFINITY, f32::min);
            let hi = px[..3].iter().copied().fold(f32::NEG_INFINITY, f32::max);
            (lo + hi) * 0.5
        }
        2 => px[..3].iter().copied().fold(f32::NEG_INFINITY, f32::max),
        3 => hsv(px)[0] as f32,
        4 => hsv(px)[1] as f32,
        5 => px[3],
        _ => px[channel - 6],
    }
}
fn replace_channel(mut px: [f32; 4], channel: usize, value: f32) -> [f32; 4] {
    let current = metric(px, channel);
    if current == value {
        return px;
    }
    match channel {
        0 | 1 => {
            for c in &mut px[..3] {
                *c += value - current;
            }
        }
        2 => {
            if current.abs() > 1e-12 {
                for c in &mut px[..3] {
                    *c *= value / current;
                }
            } else {
                px[..3].fill(value);
            }
        }
        3 | 4 => {
            let mut h = hsv(px);
            h[channel - 3] = value as f64;
            px[..3].copy_from_slice(&from_hsv(h[0], h[1], h[2]));
        }
        5 => px[3] = value,
        _ => px[channel - 6] = value,
    }
    px
}
fn bucket(px: [f32; 4]) -> u16 {
    let mut key = 0_u16;
    for v in px {
        key = (key << 4) | ((v.clamp(0.0, 1.0) * 15.0 + 0.5) as u16);
    }
    key
}
// Fixed comparison networks avoid dynamic indexing for the small pivot groups.
#[cfg(test)]
fn sort5(mut data: [f32; 5]) -> [f32; 5] {
    macro_rules! swap {
        ($a:expr,$b:expr) => {
            if data[$a] > data[$b] {
                data.swap($a, $b);
            }
        };
    }
    swap!(0, 1);
    swap!(3, 4);
    swap!(2, 4);
    swap!(2, 3);
    swap!(1, 4);
    swap!(0, 3);
    swap!(0, 2);
    swap!(1, 3);
    swap!(1, 2);
    data
}
#[inline(always)]
fn median9(mut data: [f32; 9]) -> f32 {
    macro_rules! swap {
        ($a:expr,$b:expr) => {
            if data[$a] > data[$b] {
                data.swap($a, $b);
            }
        };
    }
    swap!(0, 1);
    swap!(3, 4);
    swap!(6, 7);
    swap!(1, 2);
    swap!(4, 5);
    swap!(7, 8);
    swap!(0, 1);
    swap!(3, 4);
    swap!(6, 7);
    swap!(0, 3);
    swap!(3, 6);
    swap!(0, 3);
    swap!(1, 4);
    swap!(4, 7);
    swap!(1, 4);
    swap!(2, 5);
    swap!(5, 8);
    swap!(2, 5);
    swap!(1, 3);
    swap!(5, 7);
    swap!(2, 6);
    swap!(4, 6);
    swap!(2, 4);
    swap!(4, 6);
    data[4]
}

include!("networks.rs");

// Exact finite-float medians with static comparison networks, no SDR quantization.
#[inline(never)]
fn median(values: &mut [f32]) -> f32 {
    if values.len() == 9 {
        return median9(values.try_into().unwrap());
    }
    if values.len() <= 9 {
        for i in 1..values.len() {
            let value = values[i];
            let mut j = i;
            while j > 0 && values[j - 1] > value {
                values[j] = values[j - 1];
                j -= 1;
            }
            values[j] = value;
        }
        return values[values.len() / 2];
    }
    match values.len() {
        33 => return exact33(values),
        35 => return exact35(values),
        _ => {}
    }
    if values.len() <= 15 {
        network15(values)
    } else if values.len() <= 25 {
        network25(values)
    } else {
        network36(values)
    }
}

struct Scratch {
    neighbors: Vec<[f32; 4]>,
    values: Vec<f32>,
    keys: Vec<f32>,
}
impl Scratch {
    fn new() -> Result<Self, ()> {
        Ok(Self {
            neighbors: allocate(MAX_TAPS, [0.0; 4])?,
            values: allocate(MAX_TAPS, 0.0)?,
            keys: allocate(MAX_TAPS, 0.0)?,
        })
    }
    #[inline(never)]
    fn filter(
        &mut self,
        src: &[[f32; 4]],
        metrics: &[f32],
        position: (usize, usize, usize, usize),
        offsets: &[(i32, i32)],
        controls: (usize, usize, bool),
    ) -> [f32; 4] {
        let (mode, channel, preserve) = controls;
        let (w, h, x, y) = position;
        let n = offsets.len();
        let orig = src[y * w + x];
        for (i, (dx, dy)) in offsets.iter().enumerate() {
            let xx = (x as i64 + i64::from(*dx)).clamp(0, w as i64 - 1) as usize;
            let yy = (y as i64 + i64::from(*dy)).clamp(0, h as i64 - 1) as usize;
            self.neighbors[i] = src[yy * w + xx];
            if !metrics.is_empty() {
                self.values[i] = metrics[yy * w + xx];
                self.keys[i] = self.values[i];
            }
        }
        // Uniform neighborhoods are exact identities, including hidden RGB and alpha.
        if self.neighbors[..n].iter().all(|px| *px == orig) {
            return orig;
        }
        if mode == 2 {
            let mut out = orig;
            for (ch, dest) in out[..if preserve { 3 } else { 4 }].iter_mut().enumerate() {
                for i in 0..n {
                    self.values[i] = self.neighbors[i][ch];
                }
                *dest = median(&mut self.values[..n]);
            }
            return out;
        }
        if mode == 3 {
            let mut table = [0_u16; 128];
            let mut counts = [0_u8; 128];
            let mut first = [0_u8; 128];
            let mut best = (0_u8, usize::MAX);
            for i in 0..n {
                let key = bucket(self.neighbors[i]);
                let mut index = ((u32::from(key).wrapping_mul(2654435761) >> 25) as usize) & 127;
                while counts[index] != 0 && table[index] != key {
                    index = (index + 1) & 127;
                }
                if counts[index] == 0 {
                    table[index] = key;
                    first[index] = i as u8;
                }
                counts[index] += 1;
                let candidate = first[index] as usize;
                if counts[index] > best.0 || counts[index] == best.0 && candidate < best.1 {
                    best = (counts[index], candidate);
                }
            }
            return self.neighbors[best.1];
        }
        let middle = median(&mut self.values[..n]);
        if mode == 0 {
            replace_channel(orig, channel, middle)
        } else {
            let index = self.keys[..n]
                .iter()
                .position(|value| *value == middle)
                .unwrap();
            self.neighbors[index]
        }
    }
}
fn render(pixels: &mut [[f32; 4]], w: usize, h: usize, p: &[f64], scale: f64) -> Result<(), ()> {
    if !valid(p, scale)
        || w == 0
        || h == 0
        || w > MAX_SIDE
        || h > MAX_SIDE
        || w.checked_mul(h) != Some(pixels.len())
        || pixels.len() > MAX_PIXELS
        || pixels.iter().any(|px| {
            px.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0.0..=1.0).contains(&px[3])
        })
    {
        return Err(());
    }
    if p[7] == 0.0
        || p[9] == 100.0
        || (p[3] == 0.0 && p[4] == 0.0)
        || pixels.iter().all(|px| *px == pixels[0])
    {
        return Ok(());
    }
    let radius = [p[3] * scale * 0.5, p[4] * scale * 0.5];
    let base = radius.map(|r| r.floor() as usize);
    let frac = radius.map(|r| if p[6] == 1.0 { r - r.floor() } else { 0.0 });
    let variants = (if frac[0] > 0.0 { 2 } else { 1 }) * (if frac[1] > 0.0 { 2 } else { 1 });
    let tap_limit = MAX_TAPS / variants;
    let mut kernels = Vec::new();
    kernels.try_reserve_exact(4).map_err(|_| ())?;
    for yy in 0..=1 {
        for xx in 0..=1 {
            let weight = (if xx == 0 { 1.0 - frac[0] } else { frac[0] })
                * (if yy == 0 { 1.0 - frac[1] } else { frac[1] });
            if weight > 0.0 {
                kernels.push((weight, kernel(base[0] + xx, base[1] + yy, p[5], tap_limit)?));
            }
        }
    }
    let mut src = allocate(pixels.len(), [0.0; 4])?;
    for (dest, px) in src.iter_mut().zip(pixels.iter()) {
        dest[3] = px[3];
        for ch in 0..3 {
            dest[ch] = if px[3] > 0.0 {
                ((px[ch] as f64 / px[3] as f64).clamp(-1e6, 1e6)) as f32
            } else {
                0.0
            };
        }
    }
    let mut metrics = if p[0] < 2.0 {
        allocate(pixels.len(), 0.0)?
    } else {
        Vec::new()
    };
    for (key, px) in metrics.iter_mut().zip(src.iter()) {
        *key = metric(*px, p[1] as usize);
    }
    let mut out = allocate(pixels.len(), [0.0; 4])?;
    let mut scratch = Scratch::new()?;
    let amount = p[7] / 100.0 * (1.0 - p[9] / 100.0);
    for y in 0..h {
        for x in 0..w {
            let i = y * w + x;
            let original = src[i];
            let mut filtered = [0.0_f64; 4];
            for (weight, offsets) in &kernels {
                let px = scratch.filter(
                    &src,
                    &metrics,
                    (w, h, x, y),
                    offsets,
                    (p[0] as usize, p[1] as usize, p[2] == 1.0),
                );
                for ch in 0..4 {
                    filtered[ch] += px[ch] as f64 * weight;
                }
            }
            let filtered32 = filtered.map(|v| v as f32);
            let blend = if p[8] == 0.0 {
                amount
            } else {
                let orig_key = metric(original, p[1] as usize) as f64;
                let contrast = (metric(filtered32, p[1] as usize) as f64 - orig_key).abs()
                    / (1.0 + orig_key.abs());
                amount / (1.0 + p[8] / 100.0 * contrast)
            };
            let alpha = if p[2] == 1.0 {
                original[3] as f64
            } else {
                filtered[3]
            };
            for ch in 0..3 {
                out[i][ch] =
                    (pixels[i][ch] as f64 * (1.0 - blend) + filtered[ch] * alpha * blend) as f32;
            }
            out[i][3] = if p[2] == 1.0 {
                pixels[i][3]
            } else {
                (pixels[i][3] as f64 * (1.0 - blend) + alpha * blend) as f32
            };
            // Uniform straight neighborhoods preserve the original stored pixel exactly.
            if filtered32 == original {
                out[i] = pixels[i];
            }
        }
    }
    if out.iter().any(|px| px.iter().any(|v| !v.is_finite())) {
        return Err(());
    }
    pixels.copy_from_slice(&out);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn defaults() -> [f64; 10] {
        [2.0, 0.0, 1.0, 2.0, 0.0, 0.0, 0.0, 100.0, 0.0, 0.0]
    }
    fn run(input: &[[f32; 4]], w: usize, p: &[f64]) -> Vec<[f32; 4]> {
        let mut image = input.to_vec();
        render(&mut image, w, input.len() / w, p, 1.0).unwrap();
        image
    }
    #[test]
    fn horizontal_median_removes_spike_and_preserves_alpha() {
        let image = [
            [0.1, 0.2, 0.3, 1.0],
            [0.9, 0.8, 0.7, 1.0],
            [0.1, 0.2, 0.3, 1.0],
        ];
        let result = run(&image, 3, &defaults());
        assert_eq!(result, vec![[0.1, 0.2, 0.3, 1.0]; 3]);
    }
    #[test]
    fn rotation_width_and_rectangle_change_neighbors() {
        let image = [
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ];
        let p = defaults();
        let a = run(&image, 3, &p);
        assert_eq!(a[4][0], 0.0);
        let mut p = p;
        p[5] = 90.0;
        let b = run(&image, 3, &p);
        assert_eq!(b[4][0], 1.0);
        p[5] = 0.0;
        p[3] = 0.0;
        p[4] = 2.0;
        assert_eq!(run(&image, 3, &p), b);
    }
    #[test]
    fn independent_rgba_medians_and_alpha_policy() {
        let image = [
            [0.1, 0.9, 0.3, 1.0],
            [0.8, 0.2, 0.7, 1.0],
            [0.5, 0.5, 0.9, 1.0],
        ];
        assert_eq!(run(&image, 3, &defaults())[1], [0.5, 0.5, 0.7, 1.0]);
        let alpha = [
            [0.0, 0.0, 0.0, 0.0],
            [0.8, 0.4, 0.2, 0.5],
            [0.0, 0.0, 0.0, 0.0],
        ];
        assert_eq!(run(&alpha, 3, &defaults())[1][3], 0.5);
        let mut p = defaults();
        p[2] = 0.0;
        assert_eq!(run(&alpha, 3, &p)[1], [0.0; 4]);
    }
    #[test]
    fn selected_channel_only_and_whole_pixel_selection() {
        let image = [
            [0.1, 0.8, 0.1, 1.0],
            [0.9, 0.2, 0.5, 1.0],
            [0.4, 0.6, 0.9, 1.0],
        ];
        let mut p = defaults();
        p[0] = 0.0;
        p[1] = 6.0;
        assert_eq!(run(&image, 3, &p)[1], [0.4, 0.2, 0.5, 1.0]);
        p[0] = 1.0;
        assert_eq!(run(&image, 3, &p)[1], image[2]);
    }
    #[test]
    fn most_common_pixel_and_ties_prefer_center() {
        let image = [
            [0.1, 0.2, 0.3, 1.0],
            [0.9, 0.8, 0.7, 1.0],
            [0.1, 0.2, 0.3, 1.0],
        ];
        let mut p = defaults();
        p[0] = 3.0;
        assert_eq!(run(&image, 3, &p)[1], image[0]);
        let unique = [
            [0.1, 0.2, 0.3, 1.0],
            [0.9, 0.8, 0.7, 1.0],
            [0.4, 0.5, 0.6, 1.0],
        ];
        assert_eq!(run(&unique, 3, &p)[1], unique[1]);
    }
    #[test]
    fn fractional_radius_blends_neighbor_sizes() {
        let image = [
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ];
        let mut p = defaults();
        p[3] = 1.0;
        assert_eq!(run(&image, 3, &p)[1][0], 1.0);
        p[6] = 1.0;
        assert_eq!(run(&image, 3, &p)[1][0], 0.5);
    }
    #[test]
    fn mix_level_softness_and_identity_hdr() {
        let image = [
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ];
        let mut p = defaults();
        p[9] = 50.0;
        assert_eq!(run(&image, 3, &p)[1][0], 0.5);
        p[9] = 0.0;
        p[7] = 50.0;
        assert_eq!(run(&image, 3, &p)[1][0], 0.5);
        p[7] = 100.0;
        p[8] = 100.0;
        assert!((run(&image, 3, &p)[1][0] - 1.0 / 3.0).abs() < 1e-6);
        let hdr = [[4.0, -2.0, -0.0, 0.5], [0.1, 0.2, 0.3, 0.0]];
        p[9] = 100.0;
        let out = run(&hdr, 2, &p);
        assert_eq!(out, hdr);
        assert_eq!(out[0][2].to_bits(), hdr[0][2].to_bits());
    }
    #[test]
    fn metrics_and_hsv_replacement() {
        let red = [1.0, 0.0, 0.0, 0.5];
        let expected = [0.2126, 0.5, 1.0, 0.0, 1.0, 0.5, 1.0, 0.0, 0.0];
        for (i, value) in expected.iter().enumerate() {
            assert!((metric(red, i) - value).abs() < 1e-6);
        }
        let green = replace_channel(red, 3, 1.0 / 3.0);
        for (v, expected) in green.iter().zip([0.0, 1.0, 0.0, 0.5]) {
            assert!((v - expected).abs() < 1e-6);
        }
        assert_eq!(replace_channel(red, 4, 0.0), [1.0, 1.0, 1.0, 0.5]);
    }
    #[test]
    fn kernel_budget_symmetry_and_fractional_bounds() {
        for (x, y) in [(0, 0), (50, 1), (4097, 4097), (4097, 0), (0, 4097)] {
            let k = kernel(x, y, 138.0, MAX_TAPS).unwrap();
            assert!(!k.is_empty() && k.len() <= MAX_TAPS);
            assert_eq!(k[0], (0, 0));
            for (a, b) in &k {
                assert!(k.contains(&(-a, -b)));
            }
        }
        assert_eq!(
            kernel(1, 0, 90.0, MAX_TAPS).unwrap(),
            vec![(0, 0), (0, -1), (0, 1)]
        );
    }
    #[test]
    fn brute_force_dense_rectangular_median() {
        let image: Vec<[f32; 4]> = (0..35)
            .map(|i| {
                [
                    ((i * 17 + 3) % 29) as f32 / 29.0,
                    ((i * 13 + 2) % 31) as f32 / 31.0,
                    ((i * 5 + 7) % 23) as f32 / 23.0,
                    1.0,
                ]
            })
            .collect();
        let mut p = defaults();
        p[3] = 4.0;
        p[4] = 2.0;
        let out = run(&image, 7, &p);
        for y in 0..5 {
            for x in 0..7 {
                for ch in 0..3 {
                    let mut values = Vec::new();
                    for dy in -1..=1 {
                        for dx in -2..=2 {
                            let xx = (x as i32 + dx).clamp(0, 6) as usize;
                            let yy = (y as i32 + dy).clamp(0, 4) as usize;
                            values.push(image[yy * 7 + xx][ch]);
                        }
                    }
                    values.sort_by(f32::total_cmp);
                    assert_eq!(out[y * 7 + x][ch], values[7]);
                }
            }
        }
    }
    #[test]
    fn selection_matches_sort_for_clustered_hdr() {
        for n in 1..=MAX_TAPS {
            let inputs: Vec<f32> = (0..n)
                .map(|i| {
                    if i % 7 == 0 {
                        -1e6
                    } else if i % 11 == 0 {
                        1e6
                    } else {
                        (2.0_f32).powi(-(i as i32))
                    }
                })
                .collect();
            let mut expected = inputs.clone();
            expected.sort_by(f32::total_cmp);
            assert_eq!(median(&mut inputs.clone()), expected[n / 2]);
        }
        let mut tiny = [f32::from_bits(1), f32::from_bits(2), f32::from_bits(3)];
        assert_eq!(median(&mut tiny), f32::from_bits(2));
    }
    #[test]
    fn static_networks_match_independent_sort() {
        let mut state = 0x6ad319e5_u32;
        for n in 1..=MAX_TAPS {
            for trial in 0..512 {
                let mut values: Vec<f32> = (0..n)
                    .map(|_| {
                        state ^= state << 13;
                        state ^= state >> 17;
                        state ^= state << 5;
                        if trial % 3 == 0 {
                            (state % 7) as f32
                        } else {
                            (state as i32 as f64 / 2147.0) as f32
                        }
                    })
                    .collect();
                let mut expected = values.clone();
                expected.sort_by(f32::total_cmp);
                assert_eq!(
                    median(&mut values),
                    expected[n / 2],
                    "length {n} trial {trial}"
                );
            }
        }
        for bits in 0_u32..32768 {
            let mut values: Vec<f32> = (0..15).map(|i| ((bits >> i) & 1) as f32).collect();
            assert_eq!(
                median(&mut values),
                if bits.count_ones() >= 8 { 1.0 } else { 0.0 }
            );
        }
    }
    #[test]
    fn sampling_preserves_extents_with_fractional_budget() {
        for limit in [12, 24, MAX_TAPS] {
            for (x, y) in [(50, 1), (4096, 4096), (4096, 0), (0, 4096)] {
                let offsets = kernel(x, y, 0.0, limit).unwrap();
                assert!(offsets.len() <= limit);
                assert_eq!(offsets.iter().map(|p| p.0).max().unwrap(), x as i32);
                assert_eq!(offsets.iter().map(|p| p.1).max().unwrap(), y as i32);
            }
        }
    }
    #[test]
    fn fixed_networks_all_permutations() {
        fn permutations(values: &mut [f32], start: usize, verify: fn(&[f32])) {
            if start == values.len() {
                verify(values);
                return;
            }
            for i in start..values.len() {
                values.swap(start, i);
                permutations(values, start + 1, verify);
                values.swap(start, i);
            }
        }
        permutations(&mut [0.0, 1.0, 2.0, 3.0, 4.0], 0, |v| {
            assert_eq!(sort5(v.try_into().unwrap()), [0.0, 1.0, 2.0, 3.0, 4.0])
        });
        permutations(&mut [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], 0, |v| {
            assert_eq!(median9(v.try_into().unwrap()), 4.0)
        });
    }
    #[test]
    fn invalid_input_and_abi_leave_frame_unchanged() {
        let p = defaults();
        for (i, v) in [
            (0, 4.0),
            (1, 0.5),
            (2, 0.5),
            (3, 513.0),
            (5, 36001.0),
            (7, 101.0),
            (8, f64::NAN),
        ] {
            let mut q = p;
            q[i] = v;
            let mut image = vec![[1.0; 4]];
            assert!(render(&mut image, 1, 1, &q, 1.0).is_err());
            assert_eq!(image, vec![[1.0; 4]]);
        }
        for scale in [0.0, f64::MIN_POSITIVE, 17.0, f64::INFINITY] {
            let mut image = vec![[1.0; 4]];
            assert!(render(&mut image, 1, 1, &p, scale).is_err());
            assert_eq!(image, vec![[1.0; 4]]);
        }
        let mut image = vec![[1.0; 4], [1.0, 1.0, 1.0, -0.1]];
        let before = image.clone();
        assert!(render(&mut image, 2, 1, &p, 1.0).is_err());
        assert_eq!(image, before);
        assert_eq!(ec_render(0, 1, 1, 0, 10, 0.0, 1.0), 1);
        assert_eq!(ec_render(0, 1, 1, 0, 9, 0.0, 1.0), 1);
        assert_eq!(ec_alloc(-1), 0);
    }
}
