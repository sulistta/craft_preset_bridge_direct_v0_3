//! Original bounded six-color gradient toning for EffectCraft WASM API v1.
//! Functional approximation, not source plugin code. See ADR 027.

use std::cell::RefCell;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 41;
const MAX_PIXELS: usize = 8_388_608;
const MAX_SIDE: usize = 65_536;

fn discrete(v: f64, max: f64) -> bool {
    (0.0..=max).contains(&v) && v.fract() == 0.0
}

fn valid(p: &[f64], time: f64, scale: f64) -> bool {
    p.len() == FLAT_PARAMS
        && p.iter().all(|v| v.is_finite())
        && time.is_finite()
        && time.abs() <= 1e9
        && scale.is_finite()
        && (1.0 / MAX_SIDE as f64..=16.0).contains(&scale)
        && discrete(p[0], 7.0)
        && discrete(p[1], 2.0)
        && p[2..6].iter().all(|v| discrete(*v, 1.0))
        && p[6..30].iter().all(|v| v.abs() <= 1e6)
        && p[30..32].iter().all(|v| v.abs() <= 1000.0)
        && p[32].abs() <= 100.0
        && discrete(p[33], 2.0)
        && (0.0..=1000.0).contains(&p[34])
        && p[35].abs() <= 1e6
        && p[36].abs() <= 100.0
        && p[37].abs() <= 1e9
        && p[38..40].iter().all(|v| v.abs() <= 100.0)
        && (0.0..=100.0).contains(&p[40])
}

// RGB values are normalized only for HSL/HSV calculations. Direct RGB gradients
// retain bounded negative/HDR knot values; alpha is a coverage value in 0..1.
fn polar(rgb: [f64; 3], hsl: bool) -> [f64; 3] {
    let [r, g, b] = rgb.map(|v| v.clamp(0.0, 1.0));
    let high = r.max(g).max(b);
    let low = r.min(g).min(b);
    let d = high - low;
    let third = if hsl { (high + low) * 0.5 } else { high };
    if d == 0.0 {
        return [0.0, 0.0, third];
    }
    let hue = if high == r {
        ((g - b) / d).rem_euclid(6.0)
    } else if high == g {
        (b - r) / d + 2.0
    } else {
        (r - g) / d + 4.0
    } / 6.0;
    let sat = if hsl {
        // Avoid cancellation near black: 1-abs(2*l-1) can round to zero
        // for nonzero, valid tiny colors. This algebraic form stays finite.
        d / if third <= 0.5 {
            high + low
        } else {
            2.0 - high - low
        }
    } else {
        d / high
    };
    [hue, sat, third]
}

fn cartesian([hue, sat, third]: [f64; 3], hsl: bool) -> [f64; 3] {
    let h = hue.rem_euclid(1.0) * 6.0;
    let c = if hsl {
        (1.0 - (2.0 * third - 1.0).abs()) * sat
    } else {
        third * sat
    };
    let x = c * (1.0 - (h.rem_euclid(2.0) - 1.0).abs());
    let m = if hsl { third - c * 0.5 } else { third - c };
    let rgb = match h as usize {
        0 => [c, x, 0.0],
        1 => [x, c, 0.0],
        2 => [0.0, c, x],
        3 => [0.0, x, c],
        4 => [x, 0.0, c],
        _ => [c, 0.0, x],
    };
    rgb.map(|v| v + m)
}

fn adjust(v: f64, coefficient: f64) -> f64 {
    (if coefficient < 0.0 {
        v * (1.0 + coefficient / 100.0)
    } else {
        v + (1.0 - v) * coefficient / 100.0
    })
    .clamp(0.0, 1.0)
}

struct Gradient {
    colors: [[f64; 4]; 6],
    count: usize,
    space: usize,
    squeeze: f64,
    ease: f64,
}

impl Gradient {
    fn new(p: &[f64]) -> Self {
        let space = p[1] as usize;
        let mut colors = [[0.0; 4]; 6];
        let mut count = 0;
        for i in 0..6 {
            if i != 0 && i != 5 && p[1 + i] == 0.0 {
                continue;
            }
            let mut rgb = [p[6 + i * 4], p[7 + i * 4], p[8 + i * 4]];
            if p[37] != 0.0 || p[38] != 0.0 || p[39] != 0.0 {
                let mut hsl = polar(rgb, true);
                hsl[0] += p[37] / 360.0;
                hsl[1] = adjust(hsl[1], p[38]);
                hsl[2] = adjust(hsl[2], p[39]);
                rgb = cartesian(hsl, true);
            }
            if space != 0 {
                rgb = polar(rgb, space == 1);
            }
            colors[count] = [rgb[0], rgb[1], rgb[2], p[9 + i * 4].clamp(0.0, 1.0)];
            count += 1;
        }
        Self {
            colors,
            count,
            space,
            squeeze: (-p[32] / 25.0).exp2(),
            ease: (p[36] / 25.0).exp2(),
        }
    }

    fn at(&self, mut t: f64) -> [f64; 4] {
        if self.squeeze != 1.0 {
            t = t.powf(self.squeeze);
        }
        let position = t * (self.count - 1) as f64;
        let index = (position.floor() as usize).min(self.count - 2);
        let mut f = (position - index as f64).clamp(0.0, 1.0);
        if self.ease != 1.0 {
            let a = f.powf(self.ease);
            f = a / (a + (1.0 - f).powf(self.ease));
        }
        let mut a = self.colors[index];
        let mut b = self.colors[index + 1];
        if self.space != 0 {
            if a[1] == 0.0 {
                a[0] = b[0];
            }
            if b[1] == 0.0 {
                b[0] = a[0];
            }
            b[0] = a[0] + (b[0] - a[0] + 0.5).rem_euclid(1.0) - 0.5;
        }
        let mut out = std::array::from_fn(|ch| a[ch] + (b[ch] - a[ch]) * f);
        if self.space != 0 {
            let rgb = cartesian([out[0], out[1], out[2]], self.space == 1);
            out[..3].copy_from_slice(&rgb);
        }
        out
    }
}

fn coordinate(value: f64, p: &[f64]) -> f64 {
    let black = p[30] / 100.0;
    let white = p[31] / 100.0;
    // Explicit original convention for coincident thresholds, not an inferred BCC rule.
    let base = if white == black {
        if value >= white { 1.0 } else { 0.0 }
    } else {
        ((value - black) / (white - black)).clamp(0.0, 1.0)
    };
    let v = base * p[34] + p[35] / 100.0;
    match p[33] as usize {
        0 => v.clamp(0.0, 1.0),
        1 => {
            if (0.0..=1.0).contains(&v) {
                v
            } else {
                v.rem_euclid(1.0)
            }
        }
        _ => {
            let t = v.rem_euclid(2.0);
            if t <= 1.0 { t } else { 2.0 - t }
        }
    }
}

fn render(
    pixels: &mut [[f32; 4]],
    width: usize,
    height: usize,
    p: &[f64],
    time: f64,
    scale: f64,
) -> Result<(), ()> {
    if !valid(p, time, scale)
        || width == 0
        || height == 0
        || width > MAX_SIDE
        || height > MAX_SIDE
        || width.checked_mul(height) != Some(pixels.len())
        || pixels.len() > MAX_PIXELS
        || pixels.iter().any(|px| {
            px.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0.0..=1.0).contains(&px[3])
        })
    {
        return Err(());
    }
    if p[40] == 100.0 {
        return Ok(());
    }
    let gradient = Gradient::new(p);
    let mix = p[40] / 100.0;
    for px in pixels {
        let src = *px;
        let alpha = src[3] as f64;
        // Clean invisible RGB, with no division by a near-zero alpha in the metric.
        let rgb = if alpha == 0.0 {
            [0.0; 3]
        } else {
            [
                src[0] as f64 / alpha,
                src[1] as f64 / alpha,
                src[2] as f64 / alpha,
            ]
        };
        let channel = p[0] as usize % 4;
        let metric = if channel == 0 {
            rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
        } else {
            rgb[channel - 1]
        };
        let metric = if p[0] >= 4.0 { 1.0 - metric } else { metric };
        let color = gradient.at(coordinate(metric, p));
        let target_alpha = alpha * color[3];
        for ch in 0..3 {
            let original = if alpha == 0.0 { 0.0 } else { src[ch] as f64 };
            px[ch] = (original * mix + color[ch] * target_alpha * (1.0 - mix)) as f32;
        }
        px[3] = (alpha * mix + target_alpha * (1.0 - mix)) as f32;
    }
    Ok(())
}

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
    time: f64,
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
        match render(px, width as usize, height as usize, p, time, scale) {
            Ok(()) => 0,
            Err(()) => 1,
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn defaults() -> Vec<f64> {
        let mut p = vec![0.0; FLAT_PARAMS];
        for i in 0..6 {
            p[9 + i * 4] = 1.0;
        }
        p[26..29].fill(1.0);
        p[31] = 100.0;
        p[34] = 1.0;
        p
    }
    fn close(a: f64, b: f64) {
        assert!((a - b).abs() < 2e-6, "{a} != {b}");
    }
    fn one(src: [f32; 4], p: &[f64]) -> [f32; 4] {
        let mut pixels = [src];
        render(&mut pixels, 1, 1, p, 0.0, 1.0).unwrap();
        pixels[0]
    }
    #[test]
    fn grayscale_ramp_and_partial_alpha_are_identity() {
        let p = defaults();
        for alpha in [0.0, 0.2, 1.0] {
            for gray in [0.0, 0.3, 1.0] {
                let src = [gray * alpha, gray * alpha, gray * alpha, alpha];
                for (a, b) in one(src, &p).iter().zip(src) {
                    close(*a as f64, b as f64);
                }
            }
        }
    }
    #[test]
    fn input_channels_and_inverses_have_independent_metrics() {
        let mut p = defaults();
        for i in 0..8 {
            p[0] = i as f64;
            let base = [0.2126 * 0.1 + 0.7152 * 0.2 + 0.0722 * 0.3, 0.1, 0.2, 0.3][i % 4];
            close(
                one([0.1, 0.2, 0.3, 1.0], &p)[0] as f64,
                if i >= 4 { 1.0 - base } else { base },
            );
        }
    }
    #[test]
    fn enabled_colors_are_redistributed_and_disabled_colors_do_not_leak() {
        let mut p = defaults();
        p[14..17].copy_from_slice(&[1.0, 0.0, 0.0]); // Color 3
        assert_eq!(one([0.5, 0.5, 0.5, 1.0], &p), [0.5, 0.5, 0.5, 1.0]);
        p[3] = 1.0;
        assert_eq!(one([0.5, 0.5, 0.5, 1.0], &p), [1.0, 0.0, 0.0, 1.0]);
    }
    #[test]
    fn rgb_hsl_and_hsv_use_the_declared_color_spaces() {
        let mut p = defaults();
        p[6..9].copy_from_slice(&[1.0, 0.0, 0.0]);
        p[26..29].copy_from_slice(&[0.0, 0.0, 1.0]);
        assert_eq!(one([0.5, 0.5, 0.5, 1.0], &p), [0.5, 0.0, 0.5, 1.0]);
        for space in [1.0, 2.0] {
            p[1] = space;
            let out = one([0.5, 0.5, 0.5, 1.0], &p);
            close(out[0] as f64, 1.0);
            close(out[1] as f64, 0.0);
            close(out[2] as f64, 1.0);
        }
    }
    #[test]
    fn achromatic_endpoints_do_not_impose_arbitrary_hues() {
        let mut p = defaults();
        p[1] = 2.0;
        p[26..29].copy_from_slice(&[0.0, 1.0, 0.0]);
        let out = one([0.5, 0.5, 0.5, 1.0], &p);
        close(out[0] as f64, 0.25);
        close(out[1] as f64, 0.5);
        close(out[2] as f64, 0.25);
    }
    #[test]
    fn hue_saturation_lightness_and_ease_have_effect() {
        let mut p = defaults();
        p[6..9].copy_from_slice(&[1.0, 0.0, 0.0]);
        p[26..29].copy_from_slice(&[1.0, 0.0, 0.0]);
        p[37] = 120.0;
        let out = one([0.0, 0.0, 0.0, 1.0], &p);
        close(out[0] as f64, 0.0);
        close(out[1] as f64, 1.0);
        p[38] = -100.0;
        assert_eq!(one([0.0, 0.0, 0.0, 1.0], &p), [0.5, 0.5, 0.5, 1.0]);
        p[39] = 100.0;
        assert_eq!(one([0.0, 0.0, 0.0, 1.0], &p), [1.0; 4]);
        p = defaults();
        p[36] = 50.0;
        assert!(one([0.25, 0.25, 0.25, 1.0], &p)[0] < 0.25);
        p[36] = -50.0;
        assert!(one([0.25, 0.25, 0.25, 1.0], &p)[0] > 0.25);
    }
    #[test]
    fn threshold_squeeze_loops_and_offset_follow_original_convention() {
        let mut p = defaults();
        p[32] = 25.0;
        close(one([0.25, 0.25, 0.25, 1.0], &p)[0] as f64, 0.5);
        p = defaults();
        p[30] = 50.0;
        p[31] = 50.0;
        assert_eq!(one([0.4, 0.4, 0.4, 1.0], &p), [0.0, 0.0, 0.0, 1.0]);
        assert_eq!(one([0.6, 0.6, 0.6, 1.0], &p), [1.0; 4]);
        p = defaults();
        p[30] = 100.0;
        p[31] = 0.0;
        close(one([0.2, 0.2, 0.2, 1.0], &p)[0] as f64, 0.8);
        p = defaults();
        p[34] = 2.0;
        p[33] = 1.0;
        close(coordinate(0.7, &p), 0.4);
        close(coordinate(1.0, &p), 0.0);
        p[33] = 2.0;
        close(coordinate(0.7, &p), 0.6);
        p[35] = -100.0;
        p[34] = 1.0;
        p[33] = 1.0;
        close(coordinate(0.3, &p), 0.3);
    }
    #[test]
    fn mix_uses_premultiplied_coverage_and_preserves_exact_bypass() {
        let mut p = defaults();
        p[6..9].copy_from_slice(&[1.0, 0.0, 0.0]);
        p[9] = 0.25;
        let src = [0.0, 0.0, 0.0, 0.5];
        assert_eq!(one(src, &p), [0.125, 0.0, 0.0, 0.125]);
        p[40] = 50.0;
        assert_eq!(one(src, &p), [0.0625, 0.0, 0.0, 0.3125]);
        p[40] = 100.0;
        let hdr = [1e6, -1e6, 0.5, 0.0];
        assert_eq!(one(hdr, &p), hdr);
        p[40] = 0.0;
        assert_eq!(one(hdr, &p), [0.0; 4]);
    }
    #[test]
    fn invalid_parameters_pixels_and_dimensions_never_publish_partial_output() {
        let p = defaults();
        let original = [[0.1, 0.2, 0.3, 1.0], [0.2, 0.3, 0.4, 1.0]];
        for (index, value) in [
            (0, 8.0),
            (0, 0.5),
            (1, 3.0),
            (2, 0.5),
            (30, 1001.0),
            (34, -1.0),
            (36, 101.0),
            (37, 1e9 + 1.0),
            (40, 101.0),
            (9, f64::NAN),
        ] {
            let mut bad = p.clone();
            bad[index] = value;
            let mut pixels = original;
            assert!(render(&mut pixels, 2, 1, &bad, 0.0, 1.0).is_err());
            assert_eq!(pixels, original);
        }
        let mut pixels = original;
        assert!(render(&mut pixels, 1, 1, &p, 0.0, 1.0).is_err());
        assert_eq!(pixels, original);
        pixels[1][3] = 2.0;
        let bad = pixels;
        assert!(render(&mut pixels, 2, 1, &p, 0.0, 1.0).is_err());
        assert_eq!(pixels, bad);
        let mut pixels = original;
        assert!(render(&mut pixels, 2, 1, &p, 0.0, 0.0).is_err());
        assert_eq!(pixels, original);
    }
    #[test]
    fn color_conversion_roundtrips_and_extreme_values_stay_finite() {
        for rgb in [[0.1, 0.2, 0.3], [1.0, 0.0, 0.0], [0.0; 3], [1.0; 3]] {
            for hsl in [false, true] {
                for (a, b) in cartesian(polar(rgb, hsl), hsl).iter().zip(rgb) {
                    close(*a, b);
                }
            }
        }
        let mut p = defaults();
        p[6..30].fill(1e6);
        p[32] = 100.0;
        p[34] = 1000.0;
        p[35] = 1e6;
        p[36] = -100.0;
        p[37] = 1e9;
        p[38] = 100.0;
        p[39] = -100.0;
        for space in 0..3 {
            p[1] = space as f64;
            assert!(
                one([1e6, -1e6, 1e6, 1e-30], &p)
                    .iter()
                    .all(|v| v.is_finite())
            );
        }
    }

    #[test]
    fn tiny_hsl_knots_and_adjustments_never_generate_nonfinite_output() {
        for tiny in [1e-200, f64::MIN_POSITIVE, f64::from_bits(1)] {
            assert!(polar([tiny, 0.0, 0.0], true).iter().all(|v| v.is_finite()));
            for hue in [0.0, 120.0] {
                let mut p = defaults();
                p[6..9].copy_from_slice(&[tiny, 0.0, 0.0]);
                p[26..29].copy_from_slice(&[tiny, 0.0, 0.0]);
                p[1] = 1.0;
                p[37] = hue;
                assert!(one([0.1, 0.2, 0.3, 1.0], &p).iter().all(|v| v.is_finite()));
            }
        }
    }
}
