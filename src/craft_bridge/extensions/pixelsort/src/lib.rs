//! Original bounded whole-pixel sorting for EffectCraft API v1.
//! Independent approximation; no source plugin code or assets. See ADR 020.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 26;
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

#[derive(Clone, Copy)]
struct Entry {
    index: u32,
    group: i32,
    order: f64,
    key: f64,
    allowed: bool,
}

fn valid(p: &[f64], scale: f64) -> bool {
    p.len() == FLAT_PARAMS
        && p.iter().all(|v| v.is_finite())
        && scale.is_finite()
        && (1.0 / MAX_SIDE as f64..=16.0).contains(&scale)
        && [0.0, 1.0, 2.0].contains(&p[0])
        && [1, 4, 9]
            .iter()
            .all(|i| (-36000.0..=36000.0).contains(&p[*i]))
        && [2, 3, 11, 12].iter().all(|i| p[*i].abs() <= 1e6)
        && [5, 10].iter().all(|i| (0.0..=360.0).contains(&p[*i]))
        && [6, 7, 14, 15]
            .iter()
            .all(|i| (0.0..=65536.0).contains(&p[*i]))
        && [8, 13, 23].iter().all(|i| (0.0..=1.0).contains(&p[*i]))
        && (-1e6..=1e6).contains(&p[16])
        && [0.0, 1.0].contains(&p[17])
        && [0.0, 1.0].contains(&p[18])
        && (0.0..=9.0).contains(&p[19])
        && p[19].fract() == 0.0
        && (0.0..=1000.0).contains(&p[20])
        && (0.0..=4096.0).contains(&p[21])
        && (0.0..=1e6).contains(&p[22])
        && (0.0..=4.0).contains(&p[24])
        && p[24].fract() == 0.0
        && [0.0, 1.0, 2.0].contains(&p[25])
}

// Original deterministic mixer. All seed bits matter, including the fractional part.
fn noise(seed: f64, index: u64) -> f64 {
    let mut x = seed.to_bits() ^ index.wrapping_mul(0x9e3779b97f4a7c15);
    x = x.wrapping_add(0x9e3779b97f4a7c15);
    x = (x ^ (x >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)).wrapping_mul(0x94d049bb133111eb);
    x ^= x >> 31;
    (x >> 11) as f64 / ((1_u64 << 53) as f64)
}
fn metric(pixel: [f32; 4], kind: usize, opacity: f64) -> f64 {
    let alpha = pixel[3] as f64;
    let multiplier = if opacity == 1.0 && alpha > 0.0 {
        1.0 / alpha
    } else {
        1.0
    };
    let rgb: [f64; 3] = std::array::from_fn(|ch| {
        if opacity != 0.0 && alpha == 0.0 {
            0.0
        } else {
            (pixel[ch] as f64 * multiplier).clamp(0.0, 1e6)
        }
    });
    let min = rgb.into_iter().fold(f64::INFINITY, f64::min);
    let max = rgb.into_iter().fold(0.0, f64::max);
    match kind {
        0 => 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2],
        1 => rgb.into_iter().sum::<f64>() / 3.0,
        2 => min,
        3 | 9 => max,
        4 => rgb[0],
        5 => rgb[1],
        6 => rgb[2],
        7 => {
            let delta = max - min;
            if delta <= 1e-20 {
                return 0.0;
            }
            let h = if max == rgb[0] {
                (rgb[1] - rgb[2]) / delta
            } else if max == rgb[1] {
                2.0 + (rgb[2] - rgb[0]) / delta
            } else {
                4.0 + (rgb[0] - rgb[1]) / delta
            };
            h.rem_euclid(6.0) / 6.0
        }
        8 => {
            if max == 0.0 {
                0.0
            } else {
                (max - min) / max
            }
        }
        _ => unreachable!(),
    }
}
// Floating-point rem_euclid may round a tiny negative angle to exactly 360.
// Map that boundary to zero so a full 360-degree scope always includes it.
fn wrap_degrees(angle: f64) -> f64 {
    let value = angle.rem_euclid(360.0);
    if value >= 360.0 { 0.0 } else { value }
}
fn geometry(x: f64, y: f64, w: usize, h: usize, p: &[f64], scale: f64) -> (i32, f64, bool) {
    if p[0] == 0.0 {
        let angle = p[1].to_radians();
        let (s, c) = angle.sin_cos();
        return ((-s * x + c * y).round() as i32, c * x + s * y, true);
    }
    let center = if p[0] == 1.0 {
        [p[2], p[3]]
    } else {
        [p[11], p[12]]
    };
    let dx = x - center[0];
    let dy = y - center[1];
    let r = dx.hypot(dy);
    let angle = dy.atan2(dx).to_degrees();
    if p[0] == 1.0 {
        let a = wrap_degrees(angle - p[4]);
        let bins = w.max(h) as f64 * std::f64::consts::TAU;
        let group = (a / 360.0 * bins).floor() as i32;
        let jitter = (noise(p[22], group as u64) - 0.5) * p[8] * p[7] * scale;
        let inner = (p[6] * scale + jitter).max(0.0);
        (group, r, a < p[5] && r >= inner && r < inner + p[7] * scale)
    } else {
        let group = r.floor() as i32;
        let jitter = (noise(p[22], group as u64) - 0.5) * 360.0 * p[13];
        let a = wrap_degrees(angle - p[9] - jitter);
        let inner = p[14] * scale;
        (
            group,
            a,
            a < p[10] && r >= inner && r < inner + p[15] * scale,
        )
    }
}
fn box_axis(src: &[f32], dst: &mut [f32], w: usize, h: usize, r: usize, horizontal: bool) {
    if r == 0 {
        dst.copy_from_slice(src);
        return;
    }
    let (lines, length, step) = if horizontal { (h, w, 1) } else { (w, h, w) };
    for line in 0..lines {
        let base = if horizontal { line * w } else { line };
        let mut sum = 0.0;
        for j in 0..(r + 1).min(length) {
            sum += src[base + j * step] as f64;
        }
        for j in 0..length {
            dst[base + j * step] = (sum / (2 * r + 1) as f64).clamp(0.0, 1.0) as f32;
            if j >= r {
                sum -= src[base + (j - r) * step] as f64;
            }
            if j + r + 1 < length {
                sum += src[base + (j + r + 1) * step] as f64;
            }
        }
    }
}
fn empty<T>(n: usize) -> Result<Vec<T>, ()> {
    let mut vec = Vec::new();
    vec.try_reserve_exact(n).map_err(|_| ())?;
    Ok(vec)
}
fn write_run(
    entries: &[Entry],
    span: std::ops::Range<usize>,
    scratch: &mut Vec<u32>,
    pixels: &[[f32; 4]],
    out: &mut [[f32; 4]],
    mask: &[f32],
    p: &[f64],
) {
    scratch.clear();
    scratch.extend(span.clone().map(|i| i as u32));
    scratch.sort_unstable_by(|a, b| {
        let comparison = entries[*a as usize]
            .key
            .total_cmp(&entries[*b as usize].key);
        let comparison = if p[18] == 1.0 {
            comparison.reverse()
        } else {
            comparison
        };
        comparison.then_with(|| a.cmp(b)) // stable ties in path order without allocating a stable-sort buffer
    });
    for (destination, source) in entries[span].iter().zip(scratch.iter()) {
        let dst = destination.index as usize;
        let src = entries[*source as usize].index as usize;
        let amount = mask[dst] as f64 * (1.0 - p[23]);
        for ch in 0..4 {
            let (old, new) = if ch == 3 && p[25] == 0.0 {
                (1.0, 1.0)
            } else {
                (pixels[dst][ch] as f64, pixels[src][ch] as f64)
            };
            out[dst][ch] = ((1.0 - amount) * old + amount * new) as f32;
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
        || pixels.iter().any(|pixel| {
            pixel.iter().any(|c| !c.is_finite() || c.abs() > 1e6)
                || !(0.0..=1.0).contains(&pixel[3])
        })
    {
        return Err(());
    }
    if p[23] == 1.0 && p[24] == 0.0 && p[25] != 0.0 {
        return Ok(());
    }
    let n = pixels.len();
    let mut entries = empty(n)?;
    let mut mask = empty(n)?;
    let mut tmp = empty(n)?;
    tmp.resize(n, 0.0);
    let mut out = empty(n)?;
    out.extend_from_slice(pixels);
    let mut scratch = empty(n)?;
    for (i, pixel) in pixels.iter().enumerate() {
        let key = metric(*pixel, p[19] as usize, p[25]);
        let (group, order, allowed) = geometry((i % w) as f64, (i / w) as f64, w, h, p, scale);
        entries.push(Entry {
            index: i as u32,
            group,
            order,
            key,
            allowed,
        });
        mask.push(
            if (p[17] == 1.0 && key > p[16]) || (p[17] == 0.0 && key < p[16]) {
                1.0
            } else {
                0.0
            },
        );
        if p[25] == 0.0 {
            out[i][3] = 1.0;
        }
    }
    let r = (p[21] * scale).round() as usize;
    if r > 0 {
        box_axis(&mask, &mut tmp, w, h, r, true);
        box_axis(&tmp, &mut mask, w, h, r, false);
    }
    if p[24] != 0.0 {
        for entry in &entries {
            let i = entry.index as usize;
            let value = match p[24] as usize {
                1 => entry.key.clamp(0.0, 1.0),
                2 => mask[i] as f64,
                3 => {
                    if noise(p[22], i as u64) < p[20] / 1000.0 {
                        1.0
                    } else {
                        0.0
                    }
                }
                4 => {
                    if entry.allowed {
                        mask[i] as f64
                    } else {
                        0.0
                    }
                }
                _ => unreachable!(),
            };
            let alpha = if p[25] == 0.0 {
                1.0
            } else {
                pixels[i][3] as f64
            };
            out[i] = [
                (value * alpha) as f32,
                (value * alpha) as f32,
                (value * alpha) as f32,
                alpha as f32,
            ];
        }
    } else {
        entries.sort_unstable_by(|a, b| {
            a.group
                .cmp(&b.group)
                .then_with(|| a.order.total_cmp(&b.order))
                .then_with(|| a.index.cmp(&b.index))
        });
        let mut start = None;
        let mut group = None;
        for (i, entry) in entries.iter().enumerate() {
            let selected = entry.allowed && mask[entry.index as usize] >= 0.5;
            let restart = noise(p[22], entry.index as u64) < p[20] / 1000.0;
            if (group != Some(entry.group) || !selected || restart)
                && let Some(a) = start.take()
            {
                write_run(&entries, a..i, &mut scratch, pixels, &mut out, &mask, p);
            }
            group = Some(entry.group);
            if selected && start.is_none() {
                start = Some(i);
            }
        }
        if let Some(a) = start {
            write_run(
                &entries,
                a..entries.len(),
                &mut scratch,
                pixels,
                &mut out,
                &mask,
                p,
            );
        }
    }
    // Every fallible operation completed using temporary buffers; commit once.
    pixels.copy_from_slice(&out);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn params() -> [f64; 26] {
        [
            0.0, 0.0, 4.0, 4.0, 0.0, 360.0, 0.0, 100.0, 0.0, 0.0, 360.0, 4.0, 4.0, 0.0, 0.0, 100.0,
            -1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.273, 0.0, 0.0, 1.0,
        ]
    }
    fn texture() -> Vec<[f32; 4]> {
        (0..81)
            .map(|i| {
                let v = ((i * 31) % 79) as f32 / 79.0;
                [v, v * 0.8, v * 0.3, 1.0]
            })
            .collect()
    }
    fn bits(pixel: [f32; 4]) -> [u32; 4] {
        pixel.map(f32::to_bits)
    }
    #[test]
    fn horizontal_sorts_complete_pixels_with_stable_ties_and_reverse() {
        let mut p = params();
        p[19] = 4.0;
        let original = vec![
            [0.8, 0.1, 0.0, 1.0],
            [0.2, 0.3, 0.0, 1.0],
            [0.2, 0.5, 0.0, 1.0],
            [0.6, 0.4, 0.0, 1.0],
        ];
        let mut image = original.clone();
        render(&mut image, 4, 1, &p, 1.0).unwrap();
        assert_eq!(
            image,
            vec![original[1], original[2], original[3], original[0]]
        );
        p[18] = 1.0;
        let mut reversed = original.clone();
        render(&mut reversed, 4, 1, &p, 1.0).unwrap();
        assert_eq!(
            reversed,
            vec![original[0], original[3], original[1], original[2]]
        );
    }
    #[test]
    fn threshold_regions_are_sorted_independently() {
        let mut p = params();
        p[16] = 0.5;
        let mut image = vec![[0.9; 4], [0.6; 4], [0.1; 4], [0.8; 4], [0.7; 4]];
        let expected = vec![image[1], image[0], image[2], image[4], image[3]];
        p[25] = 2.0;
        render(&mut image, 5, 1, &p, 1.0).unwrap();
        assert_eq!(image, expected);
        p[17] = 0.0;
        let mut below = vec![[0.2, 0.2, 0.2, 1.0], [0.1, 0.1, 0.1, 1.0], [0.9; 4]];
        render(&mut below, 3, 1, &p, 1.0).unwrap();
        assert_eq!(below[0][0], 0.1);
    }
    #[test]
    fn every_pattern_is_a_whole_pixel_permutation_without_resampling() {
        let input = texture();
        let mut sorted: Vec<_> = input.iter().copied().map(bits).collect();
        sorted.sort();
        for mode in 0..3 {
            let mut p = params();
            p[0] = mode as f64;
            p[1] = 37.0;
            let mut image = input.clone();
            render(&mut image, 9, 9, &p, 1.0).unwrap();
            assert_ne!(image, input);
            let mut result: Vec<_> = image.into_iter().map(bits).collect();
            result.sort();
            assert_eq!(result, sorted);
        }
    }
    #[test]
    fn all_ten_metrics_have_explicit_values() {
        let pixel = [0.8, 0.4, 0.2, 1.0];
        let expected = [
            0.4706,
            1.4 / 3.0,
            0.2,
            0.8,
            0.8,
            0.4,
            0.2,
            1.0 / 18.0,
            0.75,
            0.8,
        ];
        for (kind, expected) in expected.into_iter().enumerate() {
            assert!((metric(pixel, kind, 1.0) - expected).abs() < 1e-6);
        }
    }
    #[test]
    fn mixing_one_is_exact_hdr_identity_and_half_is_linear() {
        let mut p = params();
        let input = vec![[2.0, -1.0, 0.2, 0.5], [0.1, 0.2, 0.3, 1.0]];
        p[23] = 1.0;
        let mut image = input.clone();
        render(&mut image, 2, 1, &p, 1.0).unwrap();
        assert_eq!(image, input);
        p[23] = 0.0;
        let mut sorted = input.clone();
        render(&mut sorted, 2, 1, &p, 1.0).unwrap();
        p[23] = 0.5;
        let mut mixed = input.clone();
        render(&mut mixed, 2, 1, &p, 1.0).unwrap();
        for i in 0..2 {
            for ch in 0..4 {
                assert!((mixed[i][ch] - (input[i][ch] + sorted[i][ch]) * 0.5).abs() < 1e-6);
            }
        }
    }
    #[test]
    fn fractional_seed_is_deterministic_and_not_rounded() {
        assert_ne!(noise(0.273, 123), noise(0.274, 123));
        let mut p = params();
        p[20] = 300.0;
        let input = texture();
        let mut a = input.clone();
        let mut b = input.clone();
        render(&mut a, 9, 9, &p, 1.0).unwrap();
        render(&mut b, 9, 9, &p, 1.0).unwrap();
        assert_eq!(a, b);
        p[22] = 0.274;
        let mut c = input;
        render(&mut c, 9, 9, &p, 1.0).unwrap();
        assert_ne!(a, c);
    }
    #[test]
    fn maximum_restarts_break_every_run_into_single_pixels() {
        let mut p = params();
        p[20] = 1000.0;
        let mut image = texture();
        let before = image.clone();
        render(&mut image, 9, 9, &p, 1.0).unwrap();
        assert_eq!(image, before);
    }
    #[test]
    fn radial_and_circular_regions_preserve_pixels_outside_scope() {
        let input = texture();
        for mode in [1.0, 2.0] {
            let mut p = params();
            p[0] = mode;
            p[5] = 120.0;
            p[10] = 120.0;
            p[6] = 2.0;
            p[14] = 2.0;
            p[7] = 3.0;
            p[15] = 3.0;
            let mut image = input.clone();
            render(&mut image, 9, 9, &p, 1.0).unwrap();
            for (i, old) in input.iter().enumerate() {
                if !geometry((i % 9) as f64, (i / 9) as f64, 9, 9, &p, 1.0).2 {
                    assert_eq!(image[i], *old);
                }
            }
            assert_eq!(image[40], input[40]);
        }
    }
    #[test]
    fn full_circle_scope_includes_the_rounded_wrap_boundary() {
        assert_eq!(wrap_degrees(-1e-16), 0.0);
        for mode in [1.0, 2.0] {
            let mut p = params();
            p[0] = mode;
            p[4] = 1e-16;
            p[9] = 1e-16;
            assert!(geometry(5.0, 4.0, 9, 9, &p, 1.0).2);
        }
    }
    #[test]
    fn mask_views_are_premultiplied_and_opacity_changes_metric() {
        let input = vec![[0.4, 0.1, 0.2, 0.5], [0.2, 0.3, 0.1, 1.0]];
        let mut p = params();
        p[24] = 1.0;
        let mut normal = input.clone();
        render(&mut normal, 2, 1, &p, 1.0).unwrap();
        p[25] = 2.0;
        let mut premult = input.clone();
        render(&mut premult, 2, 1, &p, 1.0).unwrap();
        assert_ne!(normal, premult);
        p[25] = 0.0;
        let mut opaque = input.clone();
        render(&mut opaque, 2, 1, &p, 1.0).unwrap();
        assert_eq!(opaque[0][3], 1.0);
        for show in [2.0, 3.0, 4.0] {
            p[25] = 1.0;
            p[24] = show;
            let mut view = input.clone();
            render(&mut view, 2, 1, &p, 1.0).unwrap();
            for (pixel, original) in view.iter().zip(&input) {
                assert_eq!(pixel[3], original[3]);
                assert!(pixel[0] <= pixel[3]);
                assert_eq!(pixel[0], pixel[1]);
            }
        }
    }
    #[test]
    fn blur_matches_independent_zero_padded_sum() {
        let input = [0.0, 1.0, 0.0, 0.0, 1.0];
        let mut result = [0.0; 5];
        box_axis(&input, &mut result, 5, 1, 1, true);
        for (i, actual) in result.iter().enumerate() {
            let sum = (0_usize..5)
                .filter(|j| j.abs_diff(i) <= 1)
                .map(|j| input[j])
                .sum::<f32>();
            assert!((*actual - sum / 3.0).abs() < 1e-6);
        }
    }
    #[test]
    fn invalid_parameters_scales_and_pixels_leave_frame_unchanged() {
        let input = texture();
        for i in 0..26 {
            let mut p = params();
            p[i] = f64::NAN;
            let mut image = input.clone();
            assert!(render(&mut image, 9, 9, &p, 1.0).is_err());
            assert_eq!(image, input);
        }
        for scale in [0.0, f64::from_bits(1), 17.0] {
            let mut image = input.clone();
            assert!(render(&mut image, 9, 9, &params(), scale).is_err());
            assert_eq!(image, input);
        }
        let mut p = params();
        p[0] = 0.5;
        let mut image = input.clone();
        assert!(render(&mut image, 9, 9, &p, 1.0).is_err());
        assert_eq!(image, input);
        p = params();
        p[2] = 1e6 + 1.0;
        assert!(render(&mut image, 9, 9, &p, 1.0).is_err());
        assert_eq!(image, input);
        image[0][3] = 1.1;
        let before = image.clone();
        assert!(render(&mut image, 9, 9, &params(), 1.0).is_err());
        assert_eq!(image, before);
    }
    #[test]
    fn invalid_abi_never_writes_to_foreign_or_misaligned_pointers() {
        assert_eq!(ec_alloc(-1), 0);
        ec_alloc((FLAT_PARAMS * 8 + 16) as i32);
        HOST.with(|b| b.borrow_mut()[0] = 0x12345678);
        let before = HOST.with(|b| b.borrow().clone());
        assert_eq!(ec_render(0, 1, 1, 0, 25, 0.0, 1.0), 1);
        assert_eq!(ec_render(0, 1, 1, 0, 26, 0.0, 1.0), 1);
        assert_eq!(HOST.with(|b| b.borrow().clone()), before);
    }
}
