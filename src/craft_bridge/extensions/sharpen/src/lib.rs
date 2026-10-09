//! Original bounded multiband sharpening; no Sapphire implementation or assets.
//! The kernels, transfer, quality and alpha models are independent approximations.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 15;
const MAX_PIXELS: usize = 8_388_608;
const MAX_SIDE: usize = 65_536;
type Pixel = [f32; 4];

fn valid(p: &[f64], time: f64, scale: f64) -> bool {
    p.len() == FLAT_PARAMS
        && time.is_finite()
        && scale.is_finite()
        && (1.0 / MAX_SIDE as f64..=16.0).contains(&scale)
        && p.iter().enumerate().all(|(i, &v)| {
            v.is_finite()
                && match i {
                    0 => v.fract() == 0.0 && (0.0..=1.0).contains(&v),
                    14 => v.fract() == 0.0 && (0.0..=2.0).contains(&v),
                    1 | 11..=13 => (-64.0..=64.0).contains(&v),
                    2 => (0.0..=1e6).contains(&v),
                    3 | 8 => (0.0..=8192.0).contains(&v),
                    _ => (0.0..=64.0).contains(&v),
                }
        })
}

// Edge-replicated fractional box: integer taps plus fractional outer taps.
// Rolling sums are O(pixels), including radii larger than the entire frame.
fn box_axis(src: &[Pixel], dst: &mut [Pixel], w: usize, h: usize, r: f64, horizontal: bool) {
    let n = r.floor() as isize;
    let f = r - n as f64;
    let norm = 2.0 * r + 1.0;
    let (len, lines, step) = if horizontal { (w, h, 1) } else { (h, w, w) };
    for line in 0..lines {
        let base = if horizontal { line * w } else { line };
        let at = |x: isize| src[base + x.clamp(0, len as isize - 1) as usize * step];
        let mut sum = [0.0; 4];
        let first = at(0);
        let last = at(len as isize - 1);
        for ch in 0..4 {
            sum[ch] = first[ch] as f64 * (n + 1) as f64
                + last[ch] as f64 * (n - (len as isize - 1)).max(0) as f64;
        }
        for x in 1..=n.min(len as isize - 1) {
            let px = at(x);
            for ch in 0..4 {
                sum[ch] += px[ch] as f64;
            }
        }
        for x in 0..len {
            let left = at(x as isize - n - 1);
            let right = at(x as isize + n + 1);
            for ch in 0..4 {
                dst[base + x * step][ch] =
                    ((sum[ch] + f * (left[ch] as f64 + right[ch] as f64)) / norm) as f32;
            }
            let remove = at(x as isize - n);
            let add = at(x as isize + n + 1);
            for ch in 0..4 {
                sum[ch] += add[ch] as f64 - remove[ch] as f64;
            }
        }
    }
}

fn zeros<T: Default + Clone>(n: usize) -> Result<Vec<T>, ()> {
    let mut v = Vec::new();
    v.try_reserve_exact(n).map_err(|_| ())?;
    v.resize(n, T::default());
    Ok(v)
}

fn blur(src: &[Pixel], w: usize, h: usize, r: f64) -> Result<Vec<Pixel>, ()> {
    let mut tmp = zeros(src.len())?;
    let mut out = zeros(src.len())?;
    box_axis(src, &mut tmp, w, h, r, true);
    box_axis(&tmp, &mut out, w, h, r, false);
    Ok(out)
}

fn rgb(px: Pixel, normal: bool) -> [f64; 3] {
    std::array::from_fn(|ch| {
        let v = if normal {
            if px[3] > 0.0 {
                px[ch] as f64 / px[3] as f64
            } else {
                0.0
            }
        } else {
            px[ch] as f64
        };
        v.clamp(-1e6, 1e6)
    })
}

fn luma(v: [f64; 3]) -> f64 {
    v[0] * 0.2126 + v[1] * 0.7152 + v[2] * 0.0722
}

fn render(
    pixels: &mut [Pixel],
    w: usize,
    h: usize,
    p: &[f64],
    time: f64,
    scale: f64,
) -> Result<(), ()> {
    if !valid(p, time, scale)
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
    let normal = p[14] == 1.0;
    if p[1] == 0.0
        || p[2] == 0.0
        || (p[9] == 0.0 && p[10] == 0.0)
        || p[11..14].iter().all(|v| *v == 0.0)
    {
        if p[14] == 0.0 {
            for px in pixels {
                px[3] = 1.0;
            }
        }
        return Ok(());
    }
    // Normal ignores hidden RGB and limits straight color before filtering.
    let cleaned = if normal {
        let mut v: Vec<Pixel> = zeros(pixels.len())?;
        for (dst, src) in v.iter_mut().zip(pixels.iter()) {
            let straight = rgb(*src, true);
            *dst = std::array::from_fn(|ch| {
                if ch == 3 {
                    src[3]
                } else {
                    (straight[ch] * src[3] as f64) as f32
                }
            });
        }
        Some(v)
    } else {
        None
    };
    let filter_input = cleaned.as_deref().unwrap_or(pixels);
    let mut delta: Vec<[f64; 3]> = zeros(pixels.len())?;
    let mut edge: Vec<f32> = zeros(pixels.len())?;
    if p[0] == 0.0 {
        // Telescoping four-scale detail decomposition: tiny through large.
        let mut previous: Option<Vec<Pixel>> = None;
        for band in 0..4 {
            let radius = p[3] * scale * [0.5, 1.0, 2.0, 4.0][band];
            let next = blur(filter_input, w, h, radius)?;
            let gain = p[4 + band] - 1.0;
            for i in 0..pixels.len() {
                let a = rgb(previous.as_ref().map_or(pixels[i], |v| v[i]), normal);
                let b = rgb(next[i], normal);
                for ch in 0..3 {
                    delta[i][ch] += gain * (a[ch] - b[ch]);
                }
                if band == 1 {
                    let original = rgb(pixels[i], normal);
                    edge[i] = (0..3)
                        .map(|ch| (original[ch] - b[ch]).abs())
                        .fold(0.0, f64::max) as f32;
                }
            }
            previous = Some(next);
        }
    }
    let blurred = blur(filter_input, w, h, p[8] * scale)?;
    let mut output: Vec<Pixel> = zeros(pixels.len())?;
    for i in 0..pixels.len() {
        let original = rgb(pixels[i], normal);
        let low = rgb(blurred[i], normal);
        for ch in 0..3 {
            delta[i][ch] += original[ch] - low[ch];
        }
        let strength = if p[0] == 0.0 {
            edge[i] as f64
        } else {
            (0..3)
                .map(|ch| (original[ch] - low[ch]).abs())
                .fold(0.0, f64::max)
        };
        let gate = if p[2] == 0.0 {
            0.0
        } else {
            (1.0 - strength / p[2]).clamp(0.0, 1.0)
        };
        let dy = luma(delta[i]);
        output[i] = pixels[i];
        for ch in 0..3 {
            if p[11 + ch] == 0.0 {
                continue;
            }
            let adjusted =
                original[ch] + p[1] * gate * p[11 + ch] * (p[9] * dy + p[10] * (delta[i][ch] - dy));
            output[i][ch] = (adjusted * if normal { pixels[i][3] as f64 } else { 1.0 }) as f32;
        }
        if p[14] == 0.0 {
            output[i][3] = 1.0;
        }
    }
    if output.iter().flatten().any(|v| !v.is_finite()) {
        return Err(());
    }
    pixels.copy_from_slice(&output);
    Ok(())
}

thread_local! { static HOST: RefCell<Vec<u64>> = const { RefCell::new(Vec::new()) }; }
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
#[unsafe(no_mangle)]
pub extern "C" fn ec_render(
    pixels: i32,
    w: i32,
    h: i32,
    params: i32,
    nparams: i32,
    time: f64,
    scale: f64,
) -> i32 {
    if w <= 0 || h <= 0 || nparams != FLAT_PARAMS as i32 {
        return 1;
    }
    let Some(n) = (w as usize)
        .checked_mul(h as usize)
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
        // Checked aligned and disjoint regions inside HOST, with no reallocating borrow.
        let p = unsafe { std::slice::from_raw_parts(pp as *const f64, FLAT_PARAMS) };
        let px = unsafe { std::slice::from_raw_parts_mut(xp as *mut Pixel, n) };
        match render(px, w as usize, h as usize, p, time, scale) {
            Ok(()) => 0,
            Err(()) => 1,
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn defaults() -> [f64; 15] {
        [
            0.0, 1.0, 0.15, 2.0, 3.0, 1.5, 1.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
        ]
    }
    fn texture() -> Vec<Pixel> {
        (0..35)
            .map(|i| {
                [
                    (i % 7) as f32 * 0.13,
                    (i / 7) as f32 * 0.11,
                    ((i * 3) % 11) as f32 * 0.08,
                    0.5 + (i % 3) as f32 * 0.25,
                ]
            })
            .collect()
    }
    fn frame(p: &[f64]) -> Vec<Pixel> {
        let mut px = texture();
        render(&mut px, 7, 5, p, 0.0, 1.0).unwrap();
        px
    }
    fn close(a: &[Pixel], b: &[Pixel]) {
        for (a, b) in a.iter().zip(b) {
            for ch in 0..4 {
                assert!((a[ch] - b[ch]).abs() < 3e-6, "{a:?} != {b:?}");
            }
        }
    }
    #[test]
    fn fractional_box_matches_independent_direct_sum() {
        let src = texture();
        for r in [0.0, 0.25, 1.0, 1.7, 3.25, 10.75, 131072.0] {
            for horizontal in [false, true] {
                let mut out = vec![[0.0; 4]; 35];
                box_axis(&src, &mut out, 7, 5, r, horizontal);
                // Huge radius independently counts repeated edge taps analytically.
                let n = r.floor() as isize;
                let f = r - n as f64;
                for y in 0..5 {
                    for x in 0..7 {
                        let len = if horizontal { 7 } else { 5 };
                        let pos = if horizontal { x } else { y };
                        let at = |i: isize| {
                            let i = i.clamp(0, len - 1) as usize;
                            if horizontal {
                                src[y * 7 + i]
                            } else {
                                src[i * 7 + x]
                            }
                        };
                        let mut sum = [0.0; 4];
                        for i in 0..len {
                            let lo = pos as isize - n;
                            let hi = pos as isize + n;
                            let count = if i == 0 {
                                (hi.min(0) - lo + 1).max(0)
                            } else if i == len - 1 {
                                (hi - lo.max(len - 1) + 1).max(0)
                            } else {
                                i64::from((lo..=hi).contains(&i)) as isize
                            };
                            for (ch, total) in sum.iter_mut().enumerate() {
                                *total += at(i)[ch] as f64 * count as f64;
                            }
                        }
                        for ch in 0..4 {
                            sum[ch] += f
                                * (at(pos as isize - n - 1)[ch] as f64
                                    + at(pos as isize + n + 1)[ch] as f64);
                            assert!(
                                (out[y * 7 + x][ch] as f64 - sum[ch] / (2.0 * r + 1.0)).abs()
                                    < 1e-6
                            );
                        }
                    }
                }
            }
        }
    }
    #[test]
    fn constants_and_zero_amp_identity() {
        for quality in [0.0, 1.0] {
            for opacity in [0.0, 1.0, 2.0] {
                let mut p = defaults();
                p[0] = quality;
                p[14] = opacity;
                let mut px = vec![[0.2, -0.4, 2.0, 0.5]; 35];
                let mut expected = px.clone();
                if opacity == 0.0 {
                    for v in &mut expected {
                        v[3] = 1.0;
                    }
                }
                render(&mut px, 7, 5, &p, 0.0, 1.0).unwrap();
                close(&px, &expected);
                p[1] = 0.0;
                assert_eq!(
                    frame(&p),
                    if opacity == 0.0 {
                        texture()
                            .into_iter()
                            .map(|mut px| {
                                px[3] = 1.0;
                                px
                            })
                            .collect::<Vec<_>>()
                    } else {
                        texture()
                    }
                );
            }
        }
    }
    #[test]
    fn strong_edges_rejected_and_negative_amp_softens() {
        let mut p = defaults();
        p[0] = 1.0;
        p[2] = 0.0;
        assert_eq!(frame(&p), texture());
        p[2] = 1e6;
        let sharpen = frame(&p);
        assert_ne!(sharpen, texture());
        p[1] = -1.0;
        let soften = frame(&p);
        for i in 0..35 {
            for ch in 0..3 {
                assert!(((sharpen[i][ch] + soften[i][ch]) * 0.5 - texture()[i][ch]).abs() < 1e-6);
            }
        }
    }
    #[test]
    fn each_best_band_changes_the_frame_and_fast_ignores_bands() {
        let mut p = defaults();
        p[2] = 1e6;
        p[4..8].fill(1.0);
        let baseline = frame(&p);
        for i in 4..8 {
            let mut q = p;
            q[i] = 3.0;
            assert_ne!(frame(&q), baseline);
        }
        p[0] = 1.0;
        let fast = frame(&p);
        p[4..8].fill(64.0);
        assert_eq!(frame(&p), fast);
    }
    #[test]
    fn channel_suppression_and_luma_chroma_separation() {
        let mut p = defaults();
        p[2] = 1e6;
        p[14] = 2.0;
        for i in 11..14 {
            let mut q = p;
            q[i] = 0.0;
            let out = frame(&q);
            for (a, b) in out.iter().zip(texture()) {
                assert_eq!(a[i - 11].to_bits(), b[i - 11].to_bits());
            }
        }
        p[10] = 0.0;
        let lum = frame(&p);
        for (a, b) in lum.iter().zip(texture()) {
            assert!(((a[0] - b[0]) - (a[1] - b[1])).abs() < 1e-6);
        }
        p[9] = 0.0;
        p[10] = 1.0;
        let chroma = frame(&p);
        for (a, b) in chroma.iter().zip(texture()) {
            assert!((luma(rgb(*a, false)) - luma(rgb(b, false))).abs() < 1e-6);
        }
    }
    #[test]
    fn alpha_modes_and_invisible_rgb_handling() {
        let mut p = defaults();
        p[2] = 1e6;
        let mut src = vec![
            [1.0, 0.0, 0.0, 0.0],
            [0.2, 0.3, 0.1, 0.5],
            [0.1, 0.1, 0.2, 1.0],
        ];
        let original = src.clone();
        render(&mut src, 3, 1, &p, 0.0, 1.0).unwrap();
        assert_eq!(src[0], [0.0; 4]);
        for i in 0..3 {
            assert_eq!(src[i][3], original[i][3]);
        }
        p[14] = 2.0;
        let mut premult = original.clone();
        render(&mut premult, 3, 1, &p, 0.0, 1.0).unwrap();
        assert_ne!(premult, src);
        p[14] = 0.0;
        let mut opaque = original;
        render(&mut opaque, 3, 1, &p, 0.0, 1.0).unwrap();
        assert!(opaque.iter().all(|px| px[3] == 1.0));
    }
    #[test]
    fn scale_and_time_order_are_deterministic() {
        let mut p = defaults();
        p[2] = 1e6;
        let mut half = texture();
        render(&mut half, 7, 5, &p, -1.0, 0.5).unwrap();
        p[3] *= 0.5;
        p[8] *= 0.5;
        let mut full = texture();
        render(&mut full, 7, 5, &p, 200.0, 1.0).unwrap();
        assert_eq!(half, full);
    }
    #[test]
    fn upper_bounds_and_hdr_remain_finite() {
        let p = [
            0.0, 64.0, 1e6, 8192.0, 64.0, 64.0, 64.0, 64.0, 8192.0, 64.0, 64.0, 64.0, -64.0, 64.0,
            1.0,
        ];
        let mut px = vec![[1e6, -1e6, 0.0, f32::MIN_POSITIVE], [0.2, -0.3, 1e6, 0.0]];
        render(&mut px, 2, 1, &p, 0.0, 16.0).unwrap();
        assert!(px.iter().flatten().all(|v| v.is_finite()));
    }
    #[test]
    fn invalid_calls_leave_input_unchanged() {
        for (i, v) in [
            (0, 0.5),
            (14, 3.0),
            (1, 65.0),
            (2, -0.1),
            (3, 8193.0),
            (4, -1.0),
            (11, -65.0),
            (8, f64::NAN),
        ] {
            let mut p = defaults();
            p[i] = v;
            let mut px = texture();
            let before = px.clone();
            assert!(render(&mut px, 7, 5, &p, 0.0, 1.0).is_err());
            assert_eq!(px, before);
        }
        let mut px = texture();
        let before = px.clone();
        for (w, h, scale, time) in [
            (0, 5, 1.0, 0.0),
            (8, 5, 1.0, 0.0),
            (7, 5, 0.0, 0.0),
            (7, 5, 1.0, f64::NAN),
        ] {
            assert!(render(&mut px, w, h, &defaults(), time, scale).is_err());
            assert_eq!(px, before);
        }
        px[2][3] = -0.1;
        let before = px.clone();
        assert!(render(&mut px, 7, 5, &defaults(), 0.0, 1.0).is_err());
        assert_eq!(px, before);
    }
    #[test]
    fn transparent_hidden_color_cannot_affect_normal_neighbors() {
        let mut p = defaults();
        p[2] = 1e6;
        let mut a = vec![
            [1e6, -1e6, 0.5, 0.0],
            [0.2, 0.3, 0.1, 0.5],
            [0.1, 0.1, 0.2, 1.0],
        ];
        let mut b = a.clone();
        b[0] = [0.0; 4];
        render(&mut a, 3, 1, &p, 0.0, 1.0).unwrap();
        render(&mut b, 3, 1, &p, 0.0, 1.0).unwrap();
        assert_eq!(a, b);
    }
    #[test]
    fn abi_bounds_are_checked() {
        assert_eq!(ec_render(0, 1, 1, 0, 15, 0.0, 1.0), 1);
        assert_eq!(ec_render(0, 1, 1, 0, 14, 0.0, 1.0), 1);
        assert_eq!(ec_alloc(-1), 0);
        assert_eq!(ec_alloc((MAX_PIXELS * 16 + FLAT_PARAMS * 8 + 1) as i32), 0);
    }
}
