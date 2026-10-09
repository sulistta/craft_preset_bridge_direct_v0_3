//! Original bounded directional line blur for EffectCraft API v1.
//! Independent approximation; no source plugin code or assets. See ADR 023.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 12;
const MAX_PIXELS: usize = 8_388_608;
const MAX_SIDE: usize = 65_536;

thread_local! {
    static HOST: RefCell<Vec<u64>> = const { RefCell::new(Vec::new()) };
}

const MAX_TAPS: usize = 31;

fn valid(p: &[f64], scale: f64) -> bool {
    p.len() == FLAT_PARAMS
        && p.iter().all(|v| v.is_finite())
        && scale.is_finite()
        && (1.0 / MAX_SIDE as f64..=16.0).contains(&scale)
        && (0.0..=8192.0).contains(&p[0])
        && p[1].abs() <= 36000.0
        && [2, 3, 9, 11].iter().all(|i| (0.0..=100.0).contains(&p[*i]))
        && [4, 5].iter().all(|i| (0.0..=255.0).contains(&p[*i]))
        && [6, 7].iter().all(|i| [0.0, 1.0].contains(&p[*i]))
        && (0.0..=26.0).contains(&p[8])
        && p[8].fract() == 0.0
        && (0.0..=8.0).contains(&p[10])
        && p[10].fract() == 0.0
}

#[derive(Clone, Copy)]
struct Tap {
    x: f64,
    y: f64,
    weight: f64,
}

fn kernel(p: &[f64], scale: f64) -> Result<Vec<Tap>, ()> {
    let length = p[0] * scale;
    let count = if length == 0.0 {
        1
    } else {
        let dense = (2 * (length * 0.5).floor() as usize + 1).clamp(3, MAX_TAPS);
        let thin = ((dense as f64 * (1.0 - p[2] / 100.0)).floor() as usize).max(3);
        if thin.is_multiple_of(2) {
            thin - 1
        } else {
            thin
        }
    };
    let (mut sin, mut cos) = p[1].rem_euclid(360.0).to_radians().sin_cos();
    if sin.abs() < 1e-12 {
        sin = 0.0;
    }
    if cos.abs() < 1e-12 {
        cos = 0.0;
    }
    let shift = if p[7] == 1.0 { length } else { 0.0 };
    let mut taps = Vec::new();
    taps.try_reserve_exact(count).map_err(|_| ())?;
    let mut sum = 0.0;
    for i in 0..count {
        let t = if count == 1 {
            0.0
        } else {
            2.0 * i as f64 / (count - 1) as f64 - 1.0
        };
        let distance = length * 0.5 * t - shift;
        let spread = p[3] / 100.0;
        let weight = if count == 1 {
            1.0
        } else {
            1.0 - spread + spread * t * t
        };
        taps.push(Tap {
            x: distance * cos,
            y: distance * sin,
            weight,
        });
        sum += weight;
    }
    for tap in &mut taps {
        tap.weight /= sum;
    }
    Ok(taps)
}

#[cfg(test)]
fn sample(src: &[[f32; 4]], size: [usize; 2], mut x: f64, mut y: f64, zero: bool) -> [f64; 4] {
    let [w, h] = size;
    if zero {
        if x <= -1.0 || x >= w as f64 || y <= -1.0 || y >= h as f64 {
            return [0.0; 4];
        }
    } else {
        x = x.clamp(0.0, (w - 1) as f64);
        y = y.clamp(0.0, (h - 1) as f64);
    }
    let ix = x.floor() as isize;
    let iy = y.floor() as isize;
    let fx = x - ix as f64;
    let fy = y - iy as f64;
    let mut out = [0.0; 4];
    for (dy, wy) in [(0, 1.0 - fy), (1, fy)] {
        for (dx, wx) in [(0, 1.0 - fx), (1, fx)] {
            let xx = ix + dx;
            let yy = iy + dy;
            let weight = wx * wy;
            if weight == 0.0 || xx < 0 || yy < 0 || xx >= w as isize || yy >= h as isize {
                continue;
            }
            for (dest, value) in out.iter_mut().zip(src[yy as usize * w + xx as usize]) {
                *dest += value as f64 * weight;
            }
        }
    }
    out
}

#[derive(Clone, Copy)]
struct SpatialTap {
    x: isize,
    y: isize,
    weight: f64,
}

// Bilinear weights/offsets are constant for a frame. Fold duplicate integer
// neighbors once, instead of flooring and interpolating every tap for every pixel.
fn spatial_kernel(taps: &[Tap]) -> Result<Vec<SpatialTap>, ()> {
    let mut out: Vec<SpatialTap> = Vec::new();
    out.try_reserve_exact(taps.len() * 4).map_err(|_| ())?;
    for tap in taps {
        let x = tap.x.floor() as isize;
        let y = tap.y.floor() as isize;
        let fx = tap.x - x as f64;
        let fy = tap.y - y as f64;
        for (dy, wy) in [(0, 1.0 - fy), (1, fy)] {
            for (dx, wx) in [(0, 1.0 - fx), (1, fx)] {
                let weight = tap.weight * wx * wy;
                if weight == 0.0 {
                    continue;
                }
                let (x, y) = (x + dx, y + dy);
                if let Some(existing) = out.iter_mut().find(|p| p.x == x && p.y == y) {
                    existing.weight += weight;
                } else {
                    out.push(SpatialTap { x, y, weight });
                }
            }
        }
    }
    Ok(out)
}

fn straight(pixel: [f64; 4]) -> [f64; 3] {
    std::array::from_fn(|c| {
        if pixel[3] > 0.0 {
            (pixel[c] / pixel[3]).clamp(-1e6, 1e6)
        } else {
            0.0
        }
    })
}

fn hsl(rgb: [f64; 3]) -> [f64; 3] {
    let rgb = rgb.map(|v| v.clamp(0.0, 1.0));
    let hi = rgb.into_iter().fold(0.0, f64::max);
    let lo = rgb.into_iter().fold(1.0, f64::min);
    let d = hi - lo;
    let lightness = (hi + lo) * 0.5;
    if d == 0.0 {
        return [0.0, 0.0, lightness];
    }
    let hue = if hi == rgb[0] {
        (rgb[1] - rgb[2]) / d
    } else if hi == rgb[1] {
        (rgb[2] - rgb[0]) / d + 2.0
    } else {
        (rgb[0] - rgb[1]) / d + 4.0
    };
    [
        (hue / 6.0).rem_euclid(1.0),
        d / (1.0 - (2.0 * lightness - 1.0).abs()),
        lightness,
    ]
}

fn from_hsl(value: [f64; 3]) -> [f64; 3] {
    let [h, s, l] = value;
    let h = h.rem_euclid(1.0) * 6.0;
    let chroma = (1.0 - (2.0 * l - 1.0).abs()) * s;
    let x = chroma * (1.0 - (h.rem_euclid(2.0) - 1.0).abs());
    let rgb = match h as u8 {
        0 => [chroma, x, 0.0],
        1 => [x, chroma, 0.0],
        2 => [0.0, chroma, x],
        3 => [0.0, x, chroma],
        4 => [x, 0.0, chroma],
        _ => [chroma, 0.0, x],
    };
    rgb.map(|v| v + l - chroma * 0.5)
}

fn luma(rgb: [f64; 3]) -> f64 {
    0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
}

// Own RGB blend formulas. Boost modes preserve identical inputs exactly.
fn blend(a: [f64; 3], b: [f64; 3], mode: usize) -> [f64; 3] {
    if mode == 0 {
        return b;
    }
    if mode == 6 {
        return if luma(a) >= luma(b) { a } else { b };
    }
    if mode == 7 {
        return if luma(a) <= luma(b) { a } else { b };
    }
    if (17..=20).contains(&mode) {
        let mut dest = hsl(a);
        let source = hsl(b);
        match mode {
            17 => dest[0] = source[0],
            18 => dest[1] = source[1],
            19 => {
                dest[0] = source[0];
                dest[1] = source[1];
            }
            _ => dest[2] = source[2],
        }
        return from_hsl(dest);
    }
    std::array::from_fn(|c| {
        let (a, b) = (a[c], b[c]);
        if (21..=25).contains(&mode) && a == b {
            return a;
        }
        match mode {
            1 => a.max(b),
            2 => a.min(b),
            3 => a * b,
            4 => 1.0 - (1.0 - a) * (1.0 - b),
            5 => (a - b).abs(),
            8 => 2.0 * a * b,
            9 => 0.5 * (1.0 - (1.0 - a) * (1.0 - b)),
            10 => 2.0 * (a - b).abs(),
            11 => 4.0 * (a - b).abs(),
            12 => a + b,
            13 => a - b,
            14 => {
                if a <= 0.5 {
                    2.0 * a * b
                } else {
                    1.0 - 2.0 * (1.0 - a) * (1.0 - b)
                }
            }
            15 => (1.0 - 2.0 * b) * a * a + 2.0 * a * b,
            16 => {
                if b <= 0.5 {
                    2.0 * a * b
                } else {
                    1.0 - 2.0 * (1.0 - a) * (1.0 - b)
                }
            }
            21 => ((((a + 0.25).max(0.0).powi(2) + (b + 0.25).max(0.0).powi(2)) * 0.5).sqrt()
                - 0.25)
                .clamp(-1e6, 1e6),
            22 => ((((a + 0.5).max(0.0).powi(4) + (b + 0.5).max(0.0).powi(4)) * 0.5)
                .sqrt()
                .sqrt()
                - 0.5)
                .clamp(-1e6, 1e6),
            23 => ((a * a + b * b) * 0.5).sqrt().copysign(a + b),
            24 => 1.0 - (((1.0 - a).powi(2) + (1.0 - b).powi(2)) * 0.5).sqrt(),
            25 => {
                let mean = (a + b) * 0.5;
                mean + (a - b).abs() * (mean - 0.5) * 0.5
            }
            _ => (a + b) * 0.5,
        }
    })
    .map(|v| v.clamp(-1e6, 1e6))
}

fn selected(channels: usize) -> [bool; 4] {
    match channels {
        0 => [true; 4],
        1 => [true, true, true, false],
        2 => [false, false, false, true],
        3 => [true, false, false, false],
        4 => [false, true, false, false],
        5 => [false, false, true, false],
        6 => [true, true, false, false],
        7 => [true, false, true, false],
        _ => [false, true, true, false],
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
    if p[11] == 100.0 || p[0] == 0.0 && (p[8] == 0.0 || p[9] == 0.0) {
        return Ok(());
    }
    let taps = spatial_kernel(&kernel(p, scale)?)?;
    let mut output = Vec::new();
    output.try_reserve_exact(pixels.len()).map_err(|_| ())?;
    output.resize(pixels.len(), [0.0; 4]);
    let channels = selected(p[10] as usize);
    let threshold = p[4] / 255.0;
    let deviation = p[5] / 255.0;
    let mix = p[11] / 100.0;
    let apply_mix = p[9] / 100.0;
    let mut rows = Vec::new();
    rows.try_reserve_exact(taps.len()).map_err(|_| ())?;
    for y in 0..h {
        rows.clear();
        for tap in &taps {
            let yy = y as isize + tap.y;
            if p[6] == 1.0 && (yy < 0 || yy >= h as isize) {
                continue;
            }
            let row = yy.clamp(0, h as isize - 1) as usize * w;
            rows.push((tap.x, row, tap.weight));
        }
        for x in 0..w {
            let i = y * w + x;
            let original = pixels[i].map(f64::from);
            let mut filtered = [0.0; 4];
            for (dx, row, weight) in &rows {
                let xx = x as isize + dx;
                if p[6] == 1.0 && (xx < 0 || xx >= w as isize) {
                    continue;
                }
                let input = pixels[row + xx.clamp(0, w as isize - 1) as usize];
                for (value, input) in filtered.iter_mut().zip(input) {
                    *value += weight * input as f64;
                }
            }
            for c in 0..4 {
                let delta = filtered[c] - original[c];
                filtered[c] = original[c]
                    + delta.signum() * (delta.abs() - threshold).max(0.0).min(deviation);
            }
            filtered[3] = filtered[3].clamp(0.0, 1.0);
            let base = straight(filtered);
            let applied = if p[8] == 0.0 || apply_mix == 0.0 {
                base
            } else {
                blend(straight(original), base, p[8] as usize)
            };
            let rgb: [f64; 3] = std::array::from_fn(|c| {
                (base[c] * (1.0 - apply_mix) + applied[c] * apply_mix) * filtered[3]
            });
            let result = [rgb[0], rgb[1], rgb[2], filtered[3]];
            for c in 0..4 {
                output[i][c] = if channels[c] {
                    (original[c] * mix + result[c] * (1.0 - mix)) as f32
                } else {
                    pixels[i][c]
                };
            }
            if filtered == original && (p[8] == 0.0 || apply_mix == 0.0) {
                output[i] = pixels[i];
            }
        }
    }
    if output.iter().any(|px| px.iter().any(|v| !v.is_finite())) {
        return Err(());
    }
    pixels.copy_from_slice(&output);
    Ok(())
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

#[cfg(test)]
mod tests {
    use super::*;
    fn defaults() -> [f64; 12] {
        [
            4.0, 0.0, 0.0, 0.0, 0.0, 255.0, 0.0, 0.0, 0.0, 100.0, 0.0, 0.0,
        ]
    }
    fn near(a: f64, b: f64) {
        assert!((a - b).abs() < 3e-6, "{a} != {b}");
    }
    fn close(a: &[[f32; 4]], b: &[[f32; 4]]) {
        assert_eq!(a.len(), b.len());
        for (p, q) in a.iter().zip(b) {
            for c in 0..4 {
                near(p[c] as f64, q[c] as f64);
            }
        }
    }
    #[test]
    fn horizontal_box_matches_independent_convolution() {
        let image: Vec<[f32; 4]> = (0..9).map(|i| [i as f32 / 8.0, 0.2, 0.1, 1.0]).collect();
        let expected: Vec<[f32; 4]> = (0..9_i32)
            .map(|i| {
                let red = (-2..=2)
                    .map(|d| (i + d).clamp(0, 8) as f32 / 8.0)
                    .sum::<f32>()
                    / 5.0;
                [red, 0.2, 0.1, 1.0]
            })
            .collect();
        let mut output = image;
        render(&mut output, 9, 1, &defaults(), 1.0).unwrap();
        close(&output, &expected);
    }
    #[test]
    fn rotation_and_preview_scale_follow_geometry() {
        let mut image = vec![[0.0, 0.0, 0.0, 1.0]; 81];
        image[40] = [1.0; 4];
        let mut p = defaults();
        let mut horizontal = image.clone();
        render(&mut horizontal, 9, 9, &p, 1.0).unwrap();
        near(horizontal[38][0] as f64, 0.2);
        near(horizontal[22][0] as f64, 0.0);
        p[1] = 90.0;
        let mut vertical = image.clone();
        render(&mut vertical, 9, 9, &p, 1.0).unwrap();
        near(vertical[22][0] as f64, 0.2);
        near(vertical[38][0] as f64, 0.0);
        let mut half = image;
        render(&mut half, 9, 9, &p, 0.5).unwrap();
        near(half[40][0] as f64, 1.0 / 3.0);
    }
    #[test]
    fn thin_spread_and_displacement_change_distribution() {
        let mut image = vec![[0.0, 0.0, 0.0, 1.0]; 17];
        image[8] = [1.0; 4];
        let mut p = defaults();
        let mut thin = image.clone();
        p[2] = 100.0;
        render(&mut thin, 17, 1, &p, 1.0).unwrap();
        near(thin[8][0] as f64, 1.0 / 3.0);
        near(thin[7][0] as f64, 0.0);
        let mut spread = image.clone();
        p[3] = 100.0;
        render(&mut spread, 17, 1, &p, 1.0).unwrap();
        near(spread[8][0] as f64, 0.0);
        near(spread[6][0] as f64, 0.5);
        let mut displaced = image;
        p = defaults();
        p[7] = 1.0;
        render(&mut displaced, 17, 1, &p, 1.0).unwrap();
        near(displaced[12][0] as f64, 0.2);
        near(displaced[8][0] as f64, 0.0);
    }
    #[test]
    fn zero_padding_and_replication_have_distinct_alpha() {
        let mut p = defaults();
        let image = vec![[0.2, 0.3, 0.4, 1.0]; 5];
        let mut replicated = image.clone();
        render(&mut replicated, 5, 1, &p, 1.0).unwrap();
        close(&replicated, &image);
        p[6] = 1.0;
        let mut zero = image;
        render(&mut zero, 5, 1, &p, 1.0).unwrap();
        near(zero[0][3] as f64, 0.6);
        near(zero[2][3] as f64, 1.0);
    }
    #[test]
    fn fractional_line_length_uses_bilinear_samples() {
        let mut p = defaults();
        p[0] = 1.0;
        let mut image = vec![[0.0, 0.0, 0.0, 1.0], [1.0; 4], [0.0, 0.0, 0.0, 1.0]];
        render(&mut image, 3, 1, &p, 1.0).unwrap();
        near(image[1][0] as f64, 2.0 / 3.0);
        near(image[0][0] as f64, 1.0 / 6.0);
    }
    #[test]
    fn thresholds_and_maximum_deviation_limit_changes() {
        let image = vec![[0.0, 0.0, 0.0, 1.0], [1.0; 4], [0.0, 0.0, 0.0, 1.0]];
        let mut p = defaults();
        p[0] = 2.0;
        let mut maxdev = image.clone();
        p[5] = 25.5;
        render(&mut maxdev, 3, 1, &p, 1.0).unwrap();
        near(maxdev[1][0] as f64, 0.9);
        let mut threshold = image.clone();
        p[5] = 255.0;
        p[4] = 127.5;
        render(&mut threshold, 3, 1, &p, 1.0).unwrap();
        near(threshold[1][0] as f64, 5.0 / 6.0);
        near(threshold[0][0] as f64, 0.0);
        p[4] = 255.0;
        let mut identity = image.clone();
        render(&mut identity, 3, 1, &p, 1.0).unwrap();
        assert_eq!(identity, image);
    }
    #[test]
    fn all_channel_selections_preserve_unselected_stored_components() {
        let image = vec![
            [0.1, 0.2, 0.3, 0.5],
            [0.8, 0.7, 0.6, 1.0],
            [0.1, 0.2, 0.3, 0.5],
        ];
        for selection in 0..=8 {
            let mut p = defaults();
            p[0] = 2.0;
            p[10] = selection as f64;
            let mut output = image.clone();
            render(&mut output, 3, 1, &p, 1.0).unwrap();
            let mask = selected(selection);
            for c in 0..4 {
                if !mask[c] {
                    assert_eq!(output[1][c].to_bits(), image[1][c].to_bits());
                }
            }
        }
    }
    #[test]
    fn blend_arithmetic_and_hsl_match_independent_values() {
        let a = [0.2, 0.4, 0.8];
        let b = [0.6, 0.3, 0.1];
        close(
            &[blend(a, b, 3)
                .map(|v| v as f32)
                .into_iter()
                .chain([1.0])
                .collect::<Vec<_>>()
                .try_into()
                .unwrap()],
            &[[0.12, 0.12, 0.08, 1.0]],
        );
        for c in 0..3 {
            near(blend(a, b, 4)[c], 1.0 - (1.0 - a[c]) * (1.0 - b[c]));
            near(blend(a, b, 5)[c], (a[c] - b[c]).abs());
        }
        let hue = blend([0.0, 0.0, 1.0], [1.0, 0.0, 0.0], 17);
        assert_eq!(hue, [1.0, 0.0, 0.0]);
        for mode in 21..=25 {
            assert_eq!(
                blend([-0.5, 0.25, 2.0], [-0.5, 0.25, 2.0], mode),
                [-0.5, 0.25, 2.0]
            );
        }
    }
    #[test]
    fn all_twenty_seven_blends_are_finite_for_hdr_and_transparency() {
        let image = vec![
            [0.1, 0.2, 0.3, 0.0],
            [4.0, -2.0, 0.1, 1.0],
            [0.1, 0.4, 0.2, 0.5],
        ];
        for mode in 0..=26 {
            let mut p = defaults();
            p[8] = mode as f64;
            p[6] = 1.0;
            let mut output = image.clone();
            render(&mut output, 3, 1, &p, 1.0).unwrap();
            assert!(output.iter().flatten().all(|v| v.is_finite()));
            assert!(output.iter().all(|v| (0.0..=1.0).contains(&v[3])));
        }
    }
    #[test]
    fn original_mix_and_apply_mix_have_distinct_roles() {
        let image = vec![[0.0, 0.0, 0.0, 1.0], [1.0; 4], [0.0, 0.0, 0.0, 1.0]];
        let mut p = defaults();
        p[0] = 2.0;
        let mut half = image.clone();
        p[11] = 50.0;
        render(&mut half, 3, 1, &p, 1.0).unwrap();
        near(half[1][0] as f64, 2.0 / 3.0);
        let mut full = image.clone();
        p[11] = 100.0;
        render(&mut full, 3, 1, &p, 1.0).unwrap();
        assert_eq!(full, image);
        p[11] = 0.0;
        p[8] = 12.0;
        p[9] = 0.0;
        let mut normal = image.clone();
        render(&mut normal, 3, 1, &p, 1.0).unwrap();
        near(normal[1][0] as f64, 1.0 / 3.0);
        p[9] = 100.0;
        let mut applied = image;
        render(&mut applied, 3, 1, &p, 1.0).unwrap();
        near(applied[1][0] as f64, 4.0 / 3.0);
    }
    #[test]
    fn bounded_taps_keep_center_endpoints_and_normalization() {
        for length in [0.0, 0.5, 1.0, 3.0, 67.0, 8192.0] {
            for thin in [0.0, 50.0, 100.0] {
                for spread in [0.0, 100.0] {
                    let mut p = defaults();
                    p[0] = length;
                    p[2] = thin;
                    p[3] = spread;
                    let taps = kernel(&p, 1.0).unwrap();
                    assert!(taps.len() <= MAX_TAPS && !taps.len().is_multiple_of(2));
                    near(taps.iter().map(|t| t.weight).sum(), 1.0);
                    near(taps[taps.len() / 2].x, 0.0);
                    near(taps[0].x, -length / 2.0);
                    near(taps.last().unwrap().x, length / 2.0);
                }
            }
        }
    }
    #[test]
    fn folded_kernel_matches_direct_bilinear_reference() {
        let image: Vec<[f32; 4]> = (0..247)
            .map(|i| {
                [
                    (i % 7) as f32 / 14.0,
                    (i % 5) as f32 / 10.0,
                    (i % 3) as f32 / 6.0,
                    0.5 + (i % 11) as f32 / 22.0,
                ]
            })
            .collect();
        for length in [7.25, 96.7] {
            for angle in [0.0, 37.3, 90.0, 137.3] {
                for zero in [0.0, 1.0] {
                    let mut p = defaults();
                    p[0] = length;
                    p[1] = angle;
                    p[6] = zero;
                    let taps = kernel(&p, 1.0).unwrap();
                    let mut expected = vec![[0.0; 4]; image.len()];
                    for y in 0..13 {
                        for x in 0..19 {
                            let mut sum = [0.0; 4];
                            for tap in &taps {
                                let v = sample(
                                    &image,
                                    [19, 13],
                                    x as f64 + tap.x,
                                    y as f64 + tap.y,
                                    zero == 1.0,
                                );
                                for c in 0..4 {
                                    sum[c] += tap.weight * v[c];
                                }
                            }
                            expected[y * 19 + x] = sum.map(|v| v as f32);
                        }
                    }
                    let mut actual = image.clone();
                    render(&mut actual, 19, 13, &p, 1.0).unwrap();
                    close(&actual, &expected);
                }
            }
        }
    }
    #[test]
    fn invalid_inputs_and_abi_never_mutate_the_frame() {
        for (index, value) in [
            (0, -1.0),
            (0, 8193.0),
            (1, 36001.0),
            (2, 101.0),
            (4, -1.0),
            (5, 256.0),
            (6, 0.5),
            (8, 27.0),
            (8, 0.5),
            (10, 9.0),
            (11, f64::NAN),
        ] {
            let mut p = defaults();
            p[index] = value;
            let mut image = vec![[0.3, 0.4, 0.5, 1.0]];
            let before = image.clone();
            assert!(render(&mut image, 1, 1, &p, 1.0).is_err());
            assert_eq!(image, before);
        }
        assert_eq!(ec_render(0, 1, 1, 0, FLAT_PARAMS as i32, 0.0, 1.0), 1);
        assert_eq!(ec_alloc(-1), 0);
        assert_eq!(ec_alloc(i32::MAX), 0);
        for image in [
            vec![[f32::INFINITY, 0.0, 0.0, 1.0]],
            vec![[0.0, 0.0, 0.0, 1.1]],
        ] {
            let mut image = image;
            let before = image.clone();
            assert!(render(&mut image, 1, 1, &defaults(), 1.0).is_err());
            assert_eq!(image, before);
        }
    }
}
