//! Original bounded FM modulation/demodulation for EffectCraft API v1.
//! Independent approximation; no source plugin code or assets. See ADR 018.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 12;
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

fn valid(p: &[f64], scale: f64) -> bool {
    p.len() == FLAT_PARAMS
        && p.iter().all(|x| x.is_finite())
        && scale.is_finite()
        && scale >= 1.0 / MAX_SIDE as f64
        && scale <= 16.0
        && (0.0..=4.0).contains(&p[0])
        && (0.0..=4.0).contains(&p[1])
        && (-4096.0..=4096.0).contains(&p[2])
        && (0.0..=255.0).contains(&p[8])
        && [3, 4, 5, 6, 7, 9, 10, 11]
            .iter()
            .all(|i| p[*i] == 0.0 || p[*i] == 1.0)
}
fn render(
    px: &mut [[f32; 4]],
    width: usize,
    height: usize,
    p: &[f64],
    scale: f64,
) -> Result<(), ()> {
    if !valid(p, scale)
        || width == 0
        || height == 0
        || width > MAX_SIDE
        || height > MAX_SIDE
        || width.checked_mul(height) != Some(px.len())
        || px.len() > MAX_PIXELS
        || px.iter().any(|v| {
            v.iter().any(|c| !c.is_finite() || c.abs() > 1e6) || !(0.0..=1.0).contains(&v[3])
        })
    {
        return Err(());
    }
    if p[8] == 0.0 {
        return Ok(());
    }
    // These bounded transfer functions are our calibration, not source-plugin units.
    let carrier = std::f64::consts::PI * 0.75 * p[0] / (1.0 + p[0]) / scale;
    let deviation = std::f64::consts::PI * 0.2 * p[1] / (1.0 + p[1]) / scale;
    let mix = p[8] / 255.0;
    let vertical_waves = p[10] == 0.0;
    let (lines, length) = if vertical_waves {
        (height, width)
    } else {
        (width, height)
    };
    let poles: [f64; 3] = [0.5, 0.25, 0.125].map(|a: f64| 1.0 - (1.0 - a).powf(1.0 / scale));
    for line in 0..lines {
        let mut theta = (std::f64::consts::TAU * p[1]).rem_euclid(std::f64::consts::TAU);
        let pilot = [theta.cos(), theta.sin()];
        let mut stages = [pilot; 3];
        let mut previous = pilot;
        for step in 0..length {
            let pos = if p[6] == 0.0 { step } else { length - 1 - step };
            let index = if vertical_waves {
                line * width + pos
            } else {
                pos * width + line
            };
            let source = px[index];
            let alpha = source[3] as f64;
            let luma = if alpha > 0.0 {
                (0.2126 * source[0] as f64 / alpha
                    + 0.7152 * source[1] as f64 / alpha
                    + 0.0722 * source[2] as f64 / alpha)
                    .clamp(0.0, 1.0)
            } else {
                0.0
            };
            theta = (theta + carrier + deviation * luma).rem_euclid(std::f64::consts::TAU);
            let distorted = theta + p[2] / 100.0 * theta.sin();
            let amplitude = if p[9] == 1.0 { 1.0 } else { alpha };
            let mut signal = [amplitude * distorted.cos(), amplitude * distorted.sin()];
            for stage in 0..3 {
                if p[3 + stage] == 1.0 {
                    for (dim, value) in signal.iter_mut().enumerate() {
                        *value = poles[stage] * *value + (1.0 - poles[stage]) * stages[stage][dim];
                    }
                    stages[stage] = signal;
                }
            }
            // Phase of z[n] * conjugate(z[n-1]); select the branch nearest the carrier.
            let dot = signal[0] * previous[0] + signal[1] * previous[1];
            let cross = signal[1] * previous[0] - signal[0] * previous[1];
            let delta = cross.atan2(dot);
            let unwrapped =
                delta + std::f64::consts::TAU * ((carrier - delta) / std::f64::consts::TAU).round();
            let mut gray = if deviation > 1e-12 && dot.abs() + cross.abs() > 1e-15 {
                ((unwrapped - carrier) / deviation).clamp(0.0, 1.0)
            } else {
                luma
            };
            previous = signal;
            if step == 0 && p[11] == 0.0 {
                gray = 1.0;
            }
            if p[7] == 1.0 {
                gray = 1.0 - gray;
            }
            for (dim, value) in px[index][..3].iter_mut().enumerate() {
                *value = if alpha == 0.0 {
                    0.0
                } else {
                    ((1.0 - mix) * source[dim] as f64 + mix * gray * alpha) as f32
                };
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn params() -> [f64; 12] {
        [
            0.8, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 255.0, 1.0, 0.0, 1.0,
        ]
    }
    fn texture() -> Vec<[f32; 4]> {
        (0..32)
            .map(|i| {
                let v = (i % 7) as f32 / 6.0;
                [v, 0.5 * v, 1.0 - v, 1.0]
            })
            .collect()
    }
    #[test]
    fn neutral_demod_recovers_luminance_and_premultiplied_alpha() {
        let mut image = vec![
            [0.5, 0.0, 0.0, 0.5],
            [0.0, 0.25, 0.0, 0.5],
            [0.0, 0.0, 1.0, 1.0],
            [0.0; 4],
        ];
        render(&mut image, 4, 1, &params(), 1.0).unwrap();
        for (v, expected) in image.iter().zip([0.1063, 0.1788, 0.0722, 0.0]) {
            assert!((v[0] as f64 - expected).abs() < 1e-6);
            assert_eq!(v[0], v[1]);
            assert_eq!(v[1], v[2]);
        }
        assert_eq!(image[0][3], 0.5);
        assert_eq!(image[3], [0.0; 4]);
    }
    #[test]
    fn opacity_zero_is_exact_identity() {
        let mut p = params();
        p[8] = 0.0;
        let mut image = texture();
        let before = image.clone();
        render(&mut image, 8, 4, &p, 1.0).unwrap();
        assert_eq!(image, before);
    }
    #[test]
    fn reverse_scan_matches_flipped_input() {
        let mut p = params();
        p[2] = 21.0;
        p[3] = 1.0;
        let mut forward = texture();
        let mut reverse = forward.clone();
        reverse.reverse();
        render(&mut forward, 32, 1, &p, 1.0).unwrap();
        p[6] = 1.0;
        render(&mut reverse, 32, 1, &p, 1.0).unwrap();
        reverse.reverse();
        assert_eq!(forward, reverse);
    }
    #[test]
    fn horizontal_wave_scan_equals_transpose() {
        let image = texture();
        let mut vertical = image.clone();
        let mut transposed = vec![[0.0; 4]; 32];
        for y in 0..4 {
            for x in 0..8 {
                transposed[x * 4 + y] = image[y * 8 + x];
            }
        }
        let mut p = params();
        p[2] = 19.0;
        p[4] = 1.0;
        p[10] = 1.0;
        render(&mut vertical, 8, 4, &p, 1.0).unwrap();
        p[10] = 0.0;
        render(&mut transposed, 4, 8, &p, 1.0).unwrap();
        for y in 0..4 {
            for x in 0..8 {
                assert_eq!(vertical[y * 8 + x], transposed[x * 4 + y]);
            }
        }
    }
    #[test]
    fn each_lowpass_and_omega_phase_distortion_changes_nontrivial_image() {
        let input = texture();
        let mut p = params();
        p[2] = 12.0;
        let mut baseline = input.clone();
        render(&mut baseline, 32, 1, &p, 1.0).unwrap();
        for index in [0, 1, 2, 3, 4, 5] {
            let mut changed = input.clone();
            let mut q = p;
            q[index] = if index < 3 {
                [1.3, 0.6, 26.0][index]
            } else {
                1.0
            };
            render(&mut changed, 32, 1, &q, 1.0).unwrap();
            assert_ne!(baseline, changed, "control {index}");
        }
    }
    #[test]
    fn invert_and_white_line_are_explicit() {
        let mut p = params();
        p[11] = 0.0;
        let mut image = texture();
        render(&mut image, 8, 4, &p, 1.0).unwrap();
        for y in 0..4 {
            assert_eq!(image[y * 8], [1.0; 4]);
        }
        p[7] = 1.0;
        let mut inverse = texture();
        render(&mut inverse, 8, 4, &p, 1.0).unwrap();
        for (a, b) in image.iter().zip(inverse) {
            for i in 0..3 {
                assert!((a[i] + b[i] - 1.0).abs() < 1e-6);
            }
        }
    }
    #[test]
    fn invalid_params_and_pixels_leave_buffer_unchanged() {
        for index in 0..12 {
            let mut p = params();
            p[index] = f64::NAN;
            let mut image = texture();
            let before = image.clone();
            assert!(render(&mut image, 8, 4, &p, 1.0).is_err());
            assert_eq!(image, before);
        }
        let mut p = params();
        p[6] = 0.5;
        let mut image = texture();
        let before = image.clone();
        assert!(render(&mut image, 8, 4, &p, 1.0).is_err());
        assert_eq!(image, before);
        assert!(render(&mut image, 8, 4, &params(), 0.0).is_err());
        assert_eq!(image, before);
        // Subnormal scales must not overflow frequency/phase arithmetic into NaN.
        for scale in [f64::from_bits(1), 1e-100, 0.5 / MAX_SIDE as f64] {
            assert!(render(&mut image, 8, 4, &params(), scale).is_err());
            assert_eq!(image, before);
        }
        let mut small_scale_image = texture();
        render(
            &mut small_scale_image,
            8,
            4,
            &params(),
            1.0 / MAX_SIDE as f64,
        )
        .unwrap();
        assert!(small_scale_image.iter().flatten().all(|x| x.is_finite()));
        image[0][3] = 1.01;
        let before = image.clone();
        assert!(render(&mut image, 8, 4, &params(), 1.0).is_err());
        assert_eq!(image, before);
    }

    #[test]
    fn alpha_modulates_the_carrier_without_changing_output_alpha() {
        let input = vec![
            [0.2, 0.2, 0.2, 1.0],
            [0.0; 4],
            [0.7, 0.7, 0.7, 1.0],
            [0.3, 0.3, 0.3, 0.5],
        ];
        let mut p = params();
        p[3] = 1.0;
        let mut ignore = input.clone();
        render(&mut ignore, 4, 1, &p, 1.0).unwrap();
        p[9] = 0.0;
        let mut respect = input.clone();
        render(&mut respect, 4, 1, &p, 1.0).unwrap();
        assert_ne!(ignore, respect);
        for (a, b) in respect.iter().zip(input) {
            assert_eq!(a[3], b[3]);
        }
        assert_eq!(respect[1], [0.0; 4]);
    }

    #[test]
    fn partial_opacity_is_a_linear_premultiplied_mix() {
        let mut p = params();
        let source = [0.8, 0.1, 0.3, 1.0];
        let mut full = vec![source];
        render(&mut full, 1, 1, &p, 1.0).unwrap();
        p[8] = 127.5;
        let mut half = vec![source];
        render(&mut half, 1, 1, &p, 1.0).unwrap();
        for (i, original) in source[..3].iter().enumerate() {
            assert!((half[0][i] - (original + full[0][i]) / 2.0).abs() < 1e-6);
        }
    }

    #[test]
    fn invalid_abi_call_does_not_touch_owned_allocation() {
        assert_eq!(ec_alloc(-1), 0);
        assert_eq!(
            ec_alloc(12 * 8 + 16),
            HOST.with(|b| b.borrow().as_ptr() as i32)
        );
        HOST.with(|b| b.borrow_mut()[0] = 0x123456789);
        let before = HOST.with(|b| b.borrow().clone());
        assert_eq!(ec_render(0, 1, 1, 0, 11, 0.0, 1.0), 1);
        assert_eq!(ec_render(0, 1, 1, 0, 12, 0.0, 1.0), 1);
        assert_eq!(HOST.with(|b| b.borrow().clone()), before);
    }
}
