//! Original approximate bloom for EffectCraft API v1. See docs/decisions/008.
//! This implements the Bridge's formula, not proprietary Deep Glow code.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 16;
const MAX_PIXELS: usize = 8_388_608;
type Rgb = [f32; 3];

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

fn parameters_valid(p: &[f64], scale: f64) -> bool {
    p.len() == FLAT_PARAMS
        && p.iter().all(|v| v.is_finite())
        && scale.is_finite()
        && scale > 0.0
        && scale <= 16.0
        && (0.0..=2000.0).contains(&p[0])
        && (0.0..=10000.0).contains(&p[1])
        && (0.0..=100000.0).contains(&p[2])
        && (0.0..=100.0).contains(&p[3])
        && [0.0, 1.0].contains(&p[4])
        && (0.0..=2.0).contains(&p[5])
        && [0.0, 1.0].contains(&p[6])
        && p[7..11].iter().all(|v| v.abs() <= 1_000_000.0)
        && [0.0, 1.0, 2.0].contains(&p[11])
        && (0.0..=100.0).contains(&p[12])
        && [0.0, 1.0].contains(&p[13])
        && (0.0..=100.0).contains(&p[14])
        && [0.0, 1.0].contains(&p[15])
}

// Symmetric soft threshold with explicitly defined endpoints; the proprietary knee is unknown.
fn contribution(y: f64, threshold: f64, smooth: f64) -> f64 {
    if y <= 0.0 {
        return 0.0;
    }
    if threshold == 0.0 {
        return 1.0;
    }
    let knee = threshold * smooth;
    if knee == 0.0 {
        return if y >= threshold { 1.0 } else { 0.0 };
    }
    let t = ((y - (threshold - knee)) / (2.0 * knee)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

// A zero-padded sliding box: O(pixels), with no work proportional to the radius.
// f64 sums avoid negative tails from cancellation in HDR frames.
fn box_axis(src: &[Rgb], dst: &mut [Rgb], w: usize, h: usize, r: usize, horizontal: bool) {
    if r == 0 {
        dst.copy_from_slice(src);
        return;
    }
    let (lines, length, step) = if horizontal { (h, w, 1) } else { (w, h, w) };
    let denominator = (2 * r + 1) as f64;
    for line in 0..lines {
        let base = if horizontal { line * w } else { line };
        let mut sum = [0.0_f64; 3];
        for j in 0..(r + 1).min(length) {
            for (s, v) in sum.iter_mut().zip(src[base + j * step]) {
                *s += v as f64;
            }
        }
        for j in 0..length {
            for (d, s) in dst[base + j * step].iter_mut().zip(sum) {
                *d = (s / denominator).max(0.0) as f32;
            }
            if j >= r {
                for (s, v) in sum.iter_mut().zip(src[base + (j - r) * step]) {
                    *s -= v as f64;
                }
            }
            if j + r + 1 < length {
                for (s, v) in sum.iter_mut().zip(src[base + (j + r + 1) * step]) {
                    *s += v as f64;
                }
            }
        }
    }
}

// Centered tent reduction keeps odd-grid impulses symmetric and prevents aliasing.
fn reduce_axis(src: &[Rgb], w: usize, h: usize, horizontal: bool) -> (Vec<Rgb>, usize, usize) {
    let (nw, nh) = if horizontal {
        (w.div_ceil(2), h)
    } else {
        (w, h.div_ceil(2))
    };
    let mut dst = vec![[0.0; 3]; nw * nh];
    for y in 0..nh {
        for x in 0..nw {
            let (cx, cy) = if horizontal { (2 * x, y) } else { (x, 2 * y) };
            for (delta, weight) in [(-1_isize, 0.25_f32), (0, 0.5), (1, 0.25)] {
                let (xx, yy) = if horizontal {
                    (cx as isize + delta, cy as isize)
                } else {
                    (cx as isize, cy as isize + delta)
                };
                if xx >= 0 && yy >= 0 && (xx as usize) < w && (yy as usize) < h {
                    for (d, v) in dst[y * nw + x]
                        .iter_mut()
                        .zip(src[yy as usize * w + xx as usize])
                    {
                        *d += v * weight;
                    }
                }
            }
        }
    }
    (dst, nw, nh)
}

fn accumulate(
    glow: &mut [Rgb],
    src: &[Rgb],
    size: [usize; 2],
    source_size: [usize; 2],
    factor: [usize; 2],
    weight: f32,
) {
    let [w, h] = size;
    let [sw, sh] = source_size;
    if factor == [1, 1] {
        for (g, v) in glow.iter_mut().zip(src) {
            for (c, q) in g.iter_mut().zip(v) {
                *c += q * weight;
            }
        }
        return;
    }
    for y in 0..h {
        let sy = y / factor[1];
        let ty = (y % factor[1]) as f32 / factor[1] as f32;
        for x in 0..w {
            let sx = x / factor[0];
            let tx = (x % factor[0]) as f32 / factor[0] as f32;
            let sample = |xx: usize, yy: usize| {
                if xx < sw && yy < sh {
                    src[yy * sw + xx]
                } else {
                    [0.0; 3]
                }
            };
            let a = sample(sx, sy);
            let b = sample(sx + 1, sy);
            let c = sample(sx, sy + 1);
            let d = sample(sx + 1, sy + 1);
            for ch in 0..3 {
                glow[y * w + x][ch] += ((a[ch] * (1.0 - tx) + b[ch] * tx) * (1.0 - ty)
                    + (c[ch] * (1.0 - tx) + d[ch] * tx) * ty)
                    * weight;
            }
        }
    }
}

// W3C separable blend formulas on SDR colors. HDR is intentionally an approximation.
fn tint_channel(b: f32, s: f32, mode: f64) -> f32 {
    if mode == 0.0 {
        return b * s;
    }
    let b = b.clamp(0.0, 1.0);
    let s = s.clamp(0.0, 1.0);
    if mode == 1.0 {
        if b <= 0.5 {
            2.0 * b * s
        } else {
            1.0 - 2.0 * (1.0 - b) * (1.0 - s)
        }
    } else if s <= 0.5 {
        b - (1.0 - 2.0 * s) * b * (1.0 - b)
    } else {
        let d = if b <= 0.25 {
            ((16.0 * b - 12.0) * b + 4.0) * b
        } else {
            b.sqrt()
        };
        b + (2.0 * s - 1.0) * (d - b)
    }
}

fn render(px: &mut [[f32; 4]], w: usize, h: usize, p: &[f64], scale: f64) -> Result<(), ()> {
    if w.checked_mul(h) != Some(px.len())
        || px.len() > MAX_PIXELS
        || w == 0
        || h == 0
        || !parameters_valid(p, scale)
        || px.iter().any(|x| {
            x.iter().any(|c| !c.is_finite() || c.abs() > 1_000_000.0)
                || !(0.0..=1.0).contains(&x[3])
        })
    {
        return Err(());
    }
    let mut source = vec![[0.0; 3]; px.len()];
    for (rgb, pixel) in source.iter_mut().zip(px.iter()) {
        if pixel[3] == 0.0 {
            continue;
        }
        let y = (0.2126 * pixel[0] as f64 + 0.7152 * pixel[1] as f64 + 0.0722 * pixel[2] as f64)
            / pixel[3] as f64;
        let weight = contribution(y, p[2] / 100.0, p[3] / 100.0) * p[1];
        for (d, c) in rgb.iter_mut().zip(pixel.iter()) {
            *d = (c.max(0.0) as f64 * weight) as f32;
        }
    }
    let mut glow = vec![[0.0; 3]; px.len()];
    if p[13] == 0.0 || p[0] == 0.0 {
        glow.copy_from_slice(&source);
    } else {
        let mut coarse = source;
        let (mut cw, mut ch) = (w, h);
        let mut factor = [1_usize, 1];
        // Six scales with adaptive centered reduction. This is the Bridge's kernel.
        for (i, weight) in [0.32_f32, 0.24, 0.18, 0.12, 0.08, 0.06]
            .into_iter()
            .enumerate()
        {
            let radius = p[0] * scale * (1_u32 << i) as f64 / 96.0;
            let axes = [radius * p[5], radius * (2.0 - p[5])];
            for axis in 0..2 {
                while axes[axis] / factor[axis] as f64 > 4.0
                    && (if axis == 0 { cw } else { ch }) > 1
                {
                    (coarse, cw, ch) = reduce_axis(&coarse, cw, ch, axis == 0);
                    factor[axis] *= 2;
                }
            }
            let mut work = coarse.clone();
            let mut temp = vec![[0.0; 3]; work.len()];
            let rx = (axes[0] / factor[0] as f64).round() as usize;
            let ry = (axes[1] / factor[1] as f64).round() as usize;
            for _ in 0..3 {
                box_axis(&work, &mut temp, cw, ch, rx, true);
                box_axis(&temp, &mut work, cw, ch, ry, false);
            }
            accumulate(&mut glow, &work, [w, h], [cw, ch], factor, weight);
        }
    }
    for (pixel, g) in px.iter_mut().zip(&mut glow) {
        // View Glow Input bypasses blur/tint/source composition.
        if p[13] == 1.0 {
            if p[6] == 1.0 {
                for i in 0..3 {
                    g[i] += (tint_channel(g[i], p[7 + i] as f32, p[11]) - g[i])
                        * (p[12] / 100.0) as f32;
                }
            }
            for i in 0..3 {
                let original = if pixel[3] == 0.0 {
                    0.0
                } else {
                    pixel[i] * (p[14] / 100.0) as f32
                };
                g[i] = if p[4] == 1.0 {
                    g[i] + original
                } else {
                    1.0 - (1.0 - g[i].clamp(0.0, 1.0)) * (1.0 - original.clamp(0.0, 1.0))
                };
            }
        }
        pixel[..3].copy_from_slice(g);
        pixel[3] = if p[15] == 0.0 {
            1.0
        } else {
            g.iter()
                .fold(0.0_f32, |a, c| a.max(c.abs()))
                .clamp(0.0, 1.0)
        };
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn params() -> [f64; FLAT_PARAMS] {
        [
            90.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 100.0, 1.0, 0.0, 1.0,
        ]
    }
    #[test]
    fn box_matches_brute_force_for_both_axes_and_large_radii() {
        let src: Vec<_> = (0..35).map(|i| [i as f32 * 0.1, 2.0, 0.0]).collect();
        for horizontal in [true, false] {
            for r in [0, 1, 2, 7, 100] {
                let mut out = vec![[0.0; 3]; 35];
                box_axis(&src, &mut out, 7, 5, r, horizontal);
                for y in 0..5 {
                    for x in 0..7 {
                        for c in 0..3 {
                            let mut sum = 0.0;
                            for delta in -(r as isize)..=r as isize {
                                let (xx, yy) = if horizontal {
                                    (x as isize + delta, y as isize)
                                } else {
                                    (x as isize, y as isize + delta)
                                };
                                if (0..7).contains(&xx) && (0..5).contains(&yy) {
                                    sum += src[yy as usize * 7 + xx as usize][c] as f64;
                                }
                            }
                            assert!(
                                (out[y * 7 + x][c] as f64 - sum / (2 * r + 1) as f64).abs() < 1e-6
                            );
                        }
                    }
                }
            }
        }
    }
    #[test]
    fn impulse_spreads_symmetrically_and_conserves_energy_away_from_edges() {
        let mut img = vec![[0.0; 4]; 257 * 257];
        img[128 * 257 + 128] = [4.0, 2.0, 1.0, 1.0];
        render(&mut img, 257, 257, &params(), 1.0).unwrap();
        let energy: f64 = img.iter().map(|p| p[0] as f64).sum();
        assert!((energy - 4.0).abs() < 1e-5);
        assert!(img[128 * 257 + 129][0] > img[128 * 257 + 148][0]);
        assert!(img[128 * 257 + 148][0] > 0.0);
        assert_eq!(img[128 * 257 + 129], img[129 * 257 + 128]);
    }
    #[test]
    fn exposure_does_not_change_threshold_selection_and_preserves_hdr() {
        let mut p = params();
        p[0] = 0.0;
        p[2] = 100.0;
        p[1] = 4.0;
        let mut img = [[0.25, 0.25, 0.25, 1.0], [2.0, 2.0, 2.0, 1.0]];
        render(&mut img, 2, 1, &p, 1.0).unwrap();
        assert_eq!(img[0], [0.0; 4]);
        assert_eq!(img[1], [8.0, 8.0, 8.0, 1.0]);
    }
    #[test]
    fn premultiplied_input_is_thresholded_in_straight_color() {
        let mut p = params();
        p[0] = 0.0;
        p[2] = 100.0;
        let mut img = [[0.75, 0.75, 0.75, 0.5], [1.0, 1.0, 1.0, 0.0]];
        render(&mut img, 2, 1, &p, 1.0).unwrap();
        assert_eq!(img[0], [0.75; 4]);
        assert_eq!(img[1], [0.0; 4]);
    }
    #[test]
    fn aspect_extremes_only_blur_one_axis() {
        for aspect in [0.0, 2.0] {
            let mut p = params();
            p[5] = aspect;
            let mut img = vec![[0.0; 4]; 33 * 33];
            img[16 * 33 + 16] = [1.0; 4];
            render(&mut img, 33, 33, &p, 1.0).unwrap();
            assert_eq!(img[17 * 33 + 17], [0.0; 4]);
            assert!(img[16 * 33 + 17][0] > 0.0 || img[17 * 33 + 16][0] > 0.0);
        }
    }
    #[test]
    fn view_screen_add_tint_and_unmult_have_observable_effects() {
        let mut p = params();
        p[0] = 0.0;
        p[14] = 100.0;
        let mut img = [[0.5, 0.25, 0.125, 1.0]];
        render(&mut img, 1, 1, &p, 1.0).unwrap();
        assert_eq!(img, [[1.0, 0.5, 0.25, 1.0]]);
        p[4] = 0.0;
        render(&mut img, 1, 1, &p, 1.0).unwrap();
        assert!(img[0][1] < 1.0);
        p[13] = 0.0;
        p[15] = 0.0;
        let mut img = [[0.2, 0.3, 0.4, 0.5]];
        render(&mut img, 1, 1, &p, 1.0).unwrap();
        assert_eq!(img[0], [0.2, 0.3, 0.4, 1.0]);
        p[13] = 1.0;
        p[14] = 0.0;
        p[6] = 1.0;
        let mut img = [[0.2, 0.3, 0.4, 0.5]];
        render(&mut img, 1, 1, &p, 1.0).unwrap();
        assert!((img[0][0] - 0.2).abs() < 1e-6);
        assert_eq!(img[0][1..], [0.0, 0.0, 1.0]);
        assert!((tint_channel(0.25, 0.8, 1.0) - 0.4).abs() < 1e-6);
        assert!((tint_channel(0.25, 0.8, 2.0) - 0.4).abs() < 1e-6);
    }
    #[test]
    fn rejected_parameters_or_pixels_do_not_mutate_frame() {
        for edit in 0..6 {
            let mut p = params();
            let mut img = [[0.25; 4]];
            match edit {
                0 => p[0] = 2001.0,
                1 => p[4] = 0.5,
                2 => p[7] = 1_000_001.0,
                3 => p[1] = f64::NAN,
                4 => img[0][3] = -0.1,
                _ => img[0][0] = 1_000_001.0,
            }
            let original = img;
            assert!(render(&mut img, 1, 1, &p, 1.0).is_err());
            assert_eq!(img, original);
        }
    }
    #[test]
    fn preview_scale_changes_radius_but_not_pointwise_input() {
        let mut p = params();
        p[13] = 0.0;
        let original = [[0.5; 4]];
        let mut a = original;
        let mut b = original;
        render(&mut a, 1, 1, &p, 1.0).unwrap();
        render(&mut b, 1, 1, &p, 0.5).unwrap();
        assert_eq!(a, b);
    }
}
