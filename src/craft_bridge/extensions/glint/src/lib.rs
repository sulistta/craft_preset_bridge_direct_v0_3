//! Original bounded four-axis highlight rays for EffectCraft API v1.
//! Independent approximation; no source plugin code or assets. See ADR 019.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 31;
const MAX_PIXELS: usize = 8_388_608;
const MAX_SIDE: usize = 65_536;

thread_local! {
    static HOST: RefCell<Vec<u64>> = const { RefCell::new(Vec::new()) };
}

type Rgb = [f32; 3];

fn valid(p: &[f64], scale: f64) -> bool {
    p.len() == FLAT_PARAMS
        && p.iter().all(|x| x.is_finite())
        && scale.is_finite()
        && (1.0 / MAX_SIDE as f64..=16.0).contains(&scale)
        && [0, 6, 7, 8, 9, 25, 29]
            .iter()
            .all(|i| (0.0..=64.0).contains(&p[*i]))
        && (-1.0..=1.0).contains(&p[1])
        && [2, 3, 4, 11, 12, 13].iter().all(|i| p[*i].abs() <= 1e6)
        && [5, 14, 26, 27, 28]
            .iter()
            .all(|i| (0.0..=1.0).contains(&p[*i]))
        && (0.0..=1e6).contains(&p[10])
        && [15, 16, 24].iter().all(|i| (0.0..=4096.0).contains(&p[*i]))
        && p[17..24].iter().all(|x| (0.0..=8.0).contains(x))
        && [0.0, 1.0, 2.0].contains(&p[30])
}

fn buffer(n: usize) -> Result<Vec<Rgb>, ()> {
    let mut output = Vec::new();
    output.try_reserve_exact(n).map_err(|_| ())?;
    output.resize(n, [0.0; 3]);
    Ok(output)
}

// Original zero-padded sliding box. Work is O(pixels), independent of radius.
fn box_axis(src: &[Rgb], dst: &mut [Rgb], w: usize, h: usize, r: usize, horizontal: bool) {
    if r == 0 {
        dst.copy_from_slice(src);
        return;
    }
    let (lines, length, step) = if horizontal { (h, w, 1) } else { (w, h, w) };
    let denominator = (2 * r + 1) as f64;
    for line in 0..lines {
        let base = if horizontal { line * w } else { line };
        let mut sum = [0.0; 3];
        for j in 0..(r + 1).min(length) {
            for (s, value) in sum.iter_mut().zip(src[base + j * step]) {
                *s += value as f64;
            }
        }
        for j in 0..length {
            for (out, s) in dst[base + j * step].iter_mut().zip(sum) {
                *out = (s / denominator) as f32;
            }
            if j >= r {
                for (s, value) in sum.iter_mut().zip(src[base + (j - r) * step]) {
                    *s -= value as f64;
                }
            }
            if j + r + 1 < length {
                for (s, value) in sum.iter_mut().zip(src[base + (j + r + 1) * step]) {
                    *s += value as f64;
                }
            }
        }
    }
}

// Symmetric exponential kernels k[d]=(1-q)/(1+q)*q^abs(d), q=exp(-1/r).
// Four sets of non-overlapping scanlines; no work proportional to radius.
fn rays(
    src: &[Rgb],
    forward: &mut [Rgb],
    glow: &mut [Rgb],
    size: [usize; 2],
    direction: [isize; 2],
    radius: [f64; 3],
    weight: f64,
) {
    let [w, h] = size;
    let [dx, dy] = direction;
    let q = radius.map(|r| if r == 0.0 { 0.0 } else { (-1.0 / r).exp() });
    let norm = q.map(|v| (1.0 - v) / (1.0 + v));
    let inside = |x: isize, y: isize| x >= 0 && y >= 0 && x < w as isize && y < h as isize;
    for start_y in 0..h as isize {
        for start_x in 0..w as isize {
            if inside(start_x - dx, start_y - dy) {
                continue;
            }
            let (mut x, mut y) = (start_x, start_y);
            let mut state = [0.0; 3];
            while inside(x, y) {
                let index = y as usize * w + x as usize;
                for ch in 0..3 {
                    state[ch] = src[index][ch] as f64 + q[ch] * state[ch];
                    forward[index][ch] = state[ch] as f32;
                }
                x += dx;
                y += dy;
            }
            x -= dx;
            y -= dy;
            state = [0.0; 3];
            while inside(x, y) {
                let index = y as usize * w + x as usize;
                for ch in 0..3 {
                    state[ch] = src[index][ch] as f64 + q[ch] * state[ch];
                    let value =
                        norm[ch] * (forward[index][ch] as f64 + state[ch] - src[index][ch] as f64);
                    glow[index][ch] += (weight * value.max(0.0)) as f32;
                }
                x -= dx;
                y -= dy;
            }
        }
    }
}

// Original HSV rotation; no implicit gamma transform. Nonnegative HDR is supported.
fn hue(rgb: [f64; 3], shift: f64) -> [f64; 3] {
    let max = rgb.into_iter().fold(0.0, f64::max);
    let min = rgb.into_iter().fold(f64::INFINITY, f64::min);
    let delta = max - min;
    if shift == 0.0 || delta <= 1e-20 {
        return rgb;
    }
    let h = if rgb[0] == max {
        (rgb[1] - rgb[2]) / delta
    } else if rgb[1] == max {
        2.0 + (rgb[2] - rgb[0]) / delta
    } else {
        4.0 + (rgb[0] - rgb[1]) / delta
    };
    let h = (h + 6.0 * shift).rem_euclid(6.0);
    let x = delta * (1.0 - ((h % 2.0) - 1.0).abs());
    let result = match h as usize {
        0 => [delta, x, 0.0],
        1 => [x, delta, 0.0],
        2 => [0.0, delta, x],
        3 => [0.0, x, delta],
        4 => [x, 0.0, delta],
        _ => [delta, 0.0, x],
    };
    result.map(|v| v + min)
}

fn render(px: &mut [[f32; 4]], w: usize, h: usize, p: &[f64], scale: f64) -> Result<(), ()> {
    if !valid(p, scale)
        || w == 0
        || h == 0
        || w > MAX_SIDE
        || h > MAX_SIDE
        || w.checked_mul(h) != Some(px.len())
        || px.len() > MAX_PIXELS
        || px.iter().any(|v| {
            v.iter().any(|c| !c.is_finite() || c.abs() > 1e6) || !(0.0..=1.0).contains(&v[3])
        })
    {
        return Err(());
    }
    if p[0] == 0.0 && p[28] == 1.0 && p[29] == 1.0 && p[30] != 0.0 {
        return Ok(());
    }
    // Allocate all scratch space before any output mutation.
    let mut seed = buffer(px.len())?;
    let mut tmp = buffer(px.len())?;
    let mut glow = buffer(px.len())?;
    let mut forward = buffer(px.len())?;
    for (out, source) in seed.iter_mut().zip(px.iter()) {
        let alpha = source[3] as f64;
        let multiplier = if p[30] == 1.0 && alpha > 0.0 {
            1.0 / alpha
        } else {
            1.0
        };
        for ch in 0..3 {
            out[ch] = if alpha == 0.0 && p[30] != 0.0 {
                0.0
            } else {
                (source[ch] as f64 * multiplier).clamp(0.0, 1e6) as f32
            };
        }
    }
    let blur = (p[15] * scale).round() as usize;
    if blur > 0 {
        box_axis(&seed, &mut tmp, w, h, blur, true);
        box_axis(&tmp, &mut seed, w, h, blur, false);
    }
    for (input, source) in seed.iter_mut().zip(px.iter()) {
        let alpha = if p[30] == 0.0 { 1.0 } else { source[3] as f64 };
        let multiplier = if p[30] == 1.0 { alpha } else { 1.0 };
        for ch in 0..3 {
            let threshold = p[10] + p[11 + ch];
            let color = (input[ch] as f64 - threshold).max(0.0) * multiplier;
            let from_alpha = (alpha - threshold).max(0.0);
            input[ch] = ((1.0 - p[26]) * color + p[26] * from_alpha) as f32;
        }
    }
    for (axis, direction) in [[1, 0], [0, 1], [-1, 1], [1, 1]].into_iter().enumerate() {
        let weight = p[6 + axis];
        if weight == 0.0 {
            continue;
        }
        let radius = [p[21], p[22], p[23]].map(|channel| p[16] * p[17 + axis] * channel * scale);
        rays(
            &seed,
            &mut forward,
            &mut glow,
            [w, h],
            direction,
            radius,
            weight,
        );
    }
    let blur = (p[24] * scale).round() as usize;
    if blur > 0 {
        box_axis(&glow, &mut tmp, w, h, blur, true);
        box_axis(&tmp, &mut glow, w, h, blur, false);
    }
    for (source, glint) in px.iter_mut().zip(glow) {
        let rgb = hue(
            std::array::from_fn(|ch| glint[ch] as f64 * p[0] * p[2 + ch].max(0.0)),
            p[1],
        );
        let source_alpha = if p[30] == 0.0 { 1.0 } else { source[3] as f64 };
        let base_alpha = source_alpha * p[28];
        let glint_alpha = (rgb.into_iter().fold(0.0, f64::max) * p[25]).clamp(0.0, 1.0);
        let output_alpha = if p[30] == 0.0 {
            1.0
        } else {
            base_alpha + glint_alpha * (1.0 - base_alpha)
        };
        for ch in 0..3 {
            source[ch] = if output_alpha == 0.0 {
                0.0
            } else {
                (source[ch] as f64 * p[28] * p[29] + rgb[ch] * (1.0 - p[27] * base_alpha)) as f32
            };
        }
        source[3] = output_alpha as f32;
    }
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
    fn params() -> [f64; FLAT_PARAMS] {
        [
            1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.7, 0.0, 0.0, 0.0, 1.0, 0.0, 3.0,
            1.0, 1.0, 0.75, 0.75, 0.5, 1.0, 1.5, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0,
        ]
    }
    fn impulse(w: usize, h: usize) -> Vec<[f32; 4]> {
        let mut image = vec![[0.0; 4]; w * h];
        image[h / 2 * w + w / 2] = [1.0; 4];
        image
    }
    fn close(a: f64, b: f64) {
        assert!((a - b).abs() < 2e-6, "{a} != {b}");
    }
    #[test]
    fn zero_brightness_preserves_hdr_and_transparent_input_exactly() {
        let mut p = params();
        p[0] = 0.0;
        let mut image = vec![[4.0, -2.0, 0.7, 0.5], [0.9, 0.0, 0.0, 0.0]];
        let before = image.clone();
        render(&mut image, 2, 1, &p, 1.0).unwrap();
        assert_eq!(image, before);
    }
    #[test]
    fn recursive_ray_matches_independent_direct_convolution() {
        let source: Vec<Rgb> = (0..9)
            .map(|i| [(i % 3) as f32, (i % 2) as f32, 1.0])
            .collect();
        let mut forward = buffer(9).unwrap();
        let mut result = buffer(9).unwrap();
        let radius = [0.0, 1.2, 4.0];
        rays(
            &source,
            &mut forward,
            &mut result,
            [9, 1],
            [1, 0],
            radius,
            2.0,
        );
        for (i, actual) in result.iter().enumerate() {
            for ch in 0..3 {
                let q = if radius[ch] == 0.0 {
                    0.0
                } else {
                    (-1.0_f64 / radius[ch]).exp()
                };
                let expected = source
                    .iter()
                    .enumerate()
                    .map(|(j, v)| v[ch] as f64 * q.powi(i.abs_diff(j) as i32))
                    .sum::<f64>()
                    * (1.0 - q)
                    / (1.0 + q)
                    * 2.0;
                close(actual[ch] as f64, expected);
            }
        }
    }
    #[test]
    fn four_axes_and_each_channel_have_independent_extent() {
        let mut p = params();
        p[28] = 0.0;
        for axis in 0..4 {
            for brightness in &mut p[6..10] {
                *brightness = 0.0;
            }
            p[6 + axis] = 1.0;
            let mut image = impulse(9, 9);
            render(&mut image, 9, 9, &p, 1.0).unwrap();
            let [x, y] = [[5, 4], [4, 5], [3, 5], [5, 5]][axis];
            assert!(image[y * 9 + x][0] > 0.0);
            assert_eq!(image[1], [0.0; 4]);
        }
    }
    #[test]
    fn zero_size_enhances_only_the_highlight() {
        let mut p = params();
        p[16] = 0.0;
        let mut image = impulse(5, 5);
        render(&mut image, 5, 5, &p, 1.0).unwrap();
        assert!(image[12][0] > 1.0);
        assert_eq!(image[11], [0.0; 4]);
    }
    #[test]
    fn threshold_color_and_alpha_have_independent_effects() {
        let mut p = params();
        p[16] = 0.0;
        p[28] = 0.0;
        let mut image = vec![[1.0, 0.0, 0.0, 1.0]];
        p[11] = 1.0;
        render(&mut image, 1, 1, &p, 1.0).unwrap();
        assert_eq!(image, vec![[0.0; 4]]);
        p[11] = 0.0;
        p[26] = 1.0;
        let mut alpha = vec![[0.0, 0.0, 0.0, 1.0]];
        render(&mut alpha, 1, 1, &p, 1.0).unwrap();
        assert!(alpha[0][0] > 0.0);
        close(alpha[0][0] as f64, alpha[0][1] as f64);
    }
    #[test]
    fn hue_rotation_retains_hdr_value_and_tint_alpha_is_not_inferred() {
        let value = hue([2.0, 0.0, 0.0], 1.0 / 3.0);
        close(value[1], 2.0);
        close(value[0], 0.0);
        let mut p = params();
        p[16] = 0.0;
        p[28] = 0.0;
        let mut a = vec![[1.0; 4]];
        let mut b = a.clone();
        render(&mut a, 1, 1, &p, 1.0).unwrap();
        p[5] = 0.0;
        p[14] = 0.0;
        render(&mut b, 1, 1, &p, 1.0).unwrap();
        assert_eq!(a, b);
    }
    #[test]
    fn box_blur_matches_independent_zero_padded_sum() {
        let src: Vec<Rgb> = (0..12).map(|i| [i as f32, 0.0, 0.0]).collect();
        let mut dst = buffer(12).unwrap();
        box_axis(&src, &mut dst, 4, 3, 2, true);
        for y in 0..3 {
            for x in 0_usize..4 {
                let expected = (0_usize..4)
                    .filter(|j| j.abs_diff(x) <= 2)
                    .map(|j| src[y * 4 + j][0] as f64)
                    .sum::<f64>()
                    / 5.0;
                close(dst[y * 4 + x][0] as f64, expected);
            }
        }
    }
    #[test]
    fn preview_scale_and_blurs_change_the_image() {
        let p = params();
        let original = impulse(9, 9);
        let mut a = original.clone();
        render(&mut a, 9, 9, &p, 1.0).unwrap();
        for (index, value) in [(15, 1.0), (24, 1.0)] {
            let mut p = p;
            p[index] = value;
            let mut b = original.clone();
            render(&mut b, 9, 9, &p, 1.0).unwrap();
            assert_ne!(a, b);
        }
        let mut b = original;
        render(&mut b, 9, 9, &p, 0.5).unwrap();
        assert_ne!(a, b);
    }
    #[test]
    fn transparency_modes_under_source_and_brightness_are_explicit() {
        let mut p = params();
        p[16] = 0.0;
        let input = vec![[0.4, 0.4, 0.4, 0.5]];
        let mut normal = input.clone();
        render(&mut normal, 1, 1, &p, 1.0).unwrap();
        p[30] = 2.0;
        let mut premult = input.clone();
        render(&mut premult, 1, 1, &p, 1.0).unwrap();
        assert_ne!(normal, premult);
        p[30] = 0.0;
        let mut opaque = input.clone();
        render(&mut opaque, 1, 1, &p, 1.0).unwrap();
        assert_eq!(opaque[0][3], 1.0);
        p[30] = 1.0;
        p[27] = 1.0;
        let mut under = input.clone();
        render(&mut under, 1, 1, &p, 1.0).unwrap();
        assert!(under[0][0] < normal[0][0]);
        p[25] = 0.0;
        let mut no_alpha = input.clone();
        render(&mut no_alpha, 1, 1, &p, 1.0).unwrap();
        assert_eq!(no_alpha[0][3], 0.5);
        p[29] = 0.5;
        let mut dim = input;
        render(&mut dim, 1, 1, &p, 1.0).unwrap();
        assert!(dim[0][0] < no_alpha[0][0]);
    }
    #[test]
    fn invalid_parameters_pixels_and_scales_do_not_mutate() {
        let input = impulse(3, 3);
        for index in 0..FLAT_PARAMS {
            let mut p = params();
            p[index] = f64::NAN;
            let mut image = input.clone();
            assert!(render(&mut image, 3, 3, &p, 1.0).is_err());
            assert_eq!(image, input);
        }
        for scale in [0.0, f64::from_bits(1), 0.5 / 65536.0, 17.0] {
            let mut image = input.clone();
            assert!(render(&mut image, 3, 3, &params(), scale).is_err());
            assert_eq!(image, input);
        }
        let mut p = params();
        p[30] = 0.5;
        let mut image = input.clone();
        assert!(render(&mut image, 3, 3, &p, 1.0).is_err());
        assert_eq!(image, input);
        image[0][3] = 1.1;
        let before = image.clone();
        assert!(render(&mut image, 3, 3, &params(), 1.0).is_err());
        assert_eq!(image, before);
    }
    #[test]
    fn malformed_abi_call_does_not_touch_owned_allocation() {
        assert_eq!(ec_alloc(-1), 0);
        ec_alloc((FLAT_PARAMS * 8 + 16) as i32);
        HOST.with(|b| b.borrow_mut()[0] = 0x12345678);
        let before = HOST.with(|b| b.borrow().clone());
        assert_eq!(ec_render(0, 1, 1, 0, 30, 0.0, 1.0), 1);
        assert_eq!(ec_render(0, 1, 1, 0, 31, 0.0, 1.0), 1);
        assert_eq!(HOST.with(|b| b.borrow().clone()), before);
    }
}
